import logging

logger = logging.getLogger(__name__)
import asyncio
import json
import os
import re
import time

# Gemini imports
try:
    from autofill.gemini_client import get_gemini_client, EMBEDDING_DIMENSIONS
    from autofill.form_analyzer import FormAnalyzer, FieldType, FormField
except ImportError:
    # When running directly in autofill directory
    from gemini_client import get_gemini_client, EMBEDDING_DIMENSIONS
    from form_analyzer import FormAnalyzer, FieldType, FormField

# Azure AI Search Indexer
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.models import VectorizedQuery
from typing import Optional, List, Dict, Any, Tuple

# Azure Storage Blob
from azure.storage.blob import BlobServiceClient
from django.conf import settings

# params
debug = settings.SDK_DEBUG

# Azure AI Search Setup (still using Azure AI Search for vector storage)
search_endpoint = settings.AUTOFILL_AI_AZURE_AI_SEARCH_ENDPOINT
search_key = settings.AUTOFILL_AI_AZURE_AI_SEARCH_KEY
search_index_name = settings.AUTOFILL_AI_AZURE_AI_SEARCH_INDEX_NAME
# Azure AI Search Indexer
indexer = settings.AUTOFILL_AI_AZURE_AI_SEARCH_INDEXER

# Azure Storage Blob Setup
azure_storage_blob_url = settings.AUTOFILL_AI_AZURE_STORAGE_BLOB_URL
container_key = settings.AUTOFILL_AI_AZURE_STORAGE_CONTAINER_KEY
container_name = settings.AUTOFILL_AI_AZURE_STORAGE_CONTAINER_NAME
chunk_size_file = 1 * 1024 * 1024

# Gemini embedding dimensions (768 for embedding-001)
# NOTE: Azure AI Search index must be configured to support 768-dimensional vectors
# Old documents with 256 dimensions will need to be re-indexed if mixing with new documents



class AiAutofill:
    def __init__(self):

        self.question = ""
        self.session_interval = 2
        self.message = {}
        # self.query_keys = [
        #     "Biodiversity performance to date",
        #     "Biodiversity Strategy",
        # ]
        # self.keys_desc = {
        #     "Biodiversity performance to date": "Biodiversity performance is what %s has done, for example: the "
        #                                         "policies, certificates, projects they published, accomplishments "
        #                                         "regarding biodiversity conservation following the policies, "
        #                                         "certificates, projects. Objectives made to be achieved in 2025 are "
        #                                         "not performance to date. Tell me the biodiversity performance to "
        #                                         "date of %s. Describe in bullet points.",
        #     "Biodiversity Strategy": "Biodiversity strategy is the guiding principle of %s, for example: the "
        #                              "beliefs, the recognition, the reason behind the policies, certificates, "
        #                              "projects. Tell me the biodiversity strategy of %s. Describe in bullet "
        #                              "points.",
        # }

    def clean_doc_references(self, text):
        """Clean document references from text (e.g., [doc1], [doc2])."""
        return re.sub(r"\[doc\d+\]", "", text)

    async def generate_one(
        self,
        message,
        original_text=None,
        json_export=None,
        company_id=None,
        field_type: Optional[str] = None,
        field_options: Optional[List[str]] = None,
        return_structured: bool = False,
    ):
        """
        Generate text or structured data for a single datapoint using RAG.

        Args:
            message: Datapoint question/name
            original_text: Original text from datapoint (optional)
            json_export: Not used (kept for backward compatibility)
            company_id: Company ID for filtering documents (REQUIRED for RAG)
            field_type: Type of form field (text, select, radio, checkbox, etc.)
            field_options: List of options for select/radio/checkbox fields
            return_structured: If True, return structured JSON response

        Raises:
            ValueError: If company_id is not provided
        """
        if not company_id:
            raise ValueError("company_id is required for RAG autofill. All autofill requests must include company_id for proper document filtering.")

        print(f"🔵 [AUTOFILL] generate_one START - message: {message[:100]}, company_id: {company_id}, field_type: {field_type}")
        one_data = {}

        try:
            print(f"🔵 [AUTOFILL] Using RAG with company_id: {company_id}")
            rag_chat = AutofillRagChat()
            answer, references, retrieved_chunks = await asyncio.to_thread(
                rag_chat.chat,
                question=message,
                company_id=company_id,
                original_text=original_text,
                field_type=field_type,
                field_options=field_options,
            )

            print(f"🔵 [AUTOFILL] RAG chat returned - answer length: {len(answer) if answer else 0}, has_answer: {bool(answer and answer.strip())}")
            print(f"📄 [AUTOFILL] AI Response from RAG (first 500 chars): {answer[:500] if answer else 'EMPTY'}")

            # If answer is empty, return empty string to trigger upload UI in frontend
            if not answer or not answer.strip():
                print(f"🟡 [AUTOFILL] Empty answer, returning empty string for upload UI")
                one_data[message] = ""
                return one_data

            # Return structured or plain response
            if return_structured and field_type:
                try:
                    ft = FieldType(field_type) if isinstance(field_type, str) else field_type
                    parsed_value = FormAnalyzer.parse_response(answer, ft)
                    structured_response = FormAnalyzer.format_structured_response(
                        field_name=message,
                        field_type=ft,
                        value=parsed_value,
                    )
                    print(f"🟢 [AUTOFILL] Structured response: {structured_response}")
                    one_data[message] = structured_response
                except Exception as e:
                    print(f"🟡 [AUTOFILL] Failed to structure response, returning plain text: {e}")
                    one_data[message] = answer
            else:
                # Return the answer as-is (already filtered in chat method)
                print(f"🟢 [AUTOFILL] Valid answer found, length: {len(answer)}")
                print(f"📄 [AUTOFILL] Full AI Response:\n{answer}\n")
                one_data[message] = answer

            return one_data
        except Exception as e:
            print(f"🔴 [AUTOFILL] Error in RAG generate_one: {e}")
            logger.error(f"Error in RAG generate_one: {e}", exc_info=True)
            # Return empty string on error to trigger upload UI
            one_data[message] = ""
        return one_data

    async def generate_many(self, datapoints: list, batch_size: int = 10, max_concurrent: int = 5, company_id=None):
        """
        Generate text for multiple datapoints using RAG.
        
        Args:
            datapoints: List of datapoint objects
            batch_size: Batch size for processing
            max_concurrent: Max concurrent requests
            company_id: Company ID for filtering documents (REQUIRED for RAG)
        
        Raises:
            ValueError: If company_id is not provided
        """
        if not company_id:
            raise ValueError("company_id is required for RAG autofill. All autofill requests must include company_id for proper document filtering.")
        print(f"🔵 [AUTOFILL BULK] generate_many START - datapoints: {len(datapoints)}, company_id: {company_id}, batch_size: {batch_size}, max_concurrent: {max_concurrent}")
        semaphore = asyncio.Semaphore(max_concurrent)
        final_result = {}

        async def process_one(dp):
            async with semaphore:
                try:
                    print(f"🔵 [AUTOFILL BULK] Processing datapoint: {dp.name[:50]}... (ID: {dp.id})")
                    result = await asyncio.wait_for(
                        self.generate_one(dp.name, dp.original_text, None, company_id=company_id),
                        timeout=60,  # timeout for each datapoint
                    )
                    answer = result.get(dp.name, "")
                    print(f"🔵 [AUTOFILL BULK] Datapoint {dp.id} result - has_answer: {bool(answer and answer.strip())}, length: {len(answer) if answer else 0}")
                    if answer and answer.strip():
                        print(f"📄 [AUTOFILL BULK] Datapoint {dp.id} answer (first 200 chars): {answer[:200]}")
                    else:
                        print(f"🟡 [AUTOFILL BULK] Datapoint {dp.id} - no answer (answer: {repr(answer)})")
                    # Return empty string if no valid answer (for upload UI trigger)
                    if not answer or not answer.strip() or answer.strip() == "<br>":
                        return dp.name, ""
                    return dp.name, answer
                except Exception as e:
                    print(f"🔴 [AUTOFILL BULK] Error processing datapoint {dp.id}: {e}")
                    # Return empty string on error to trigger upload UI
                    return dp.name, ""

        for i in range(0, len(datapoints), batch_size):
            batch = datapoints[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(datapoints) + batch_size - 1) // batch_size
            print(f"🔵 [AUTOFILL BULK] Processing batch {batch_num}/{total_batches} - {len(batch)} datapoints")
            tasks = [process_one(dp) for dp in batch]
            results = await asyncio.gather(*tasks)
            
            # Update results - return empty string if no answer (for upload UI trigger)
            for name, text in results:
                # Check if text is valid (not None, not empty, not just whitespace, not just <br>)
                if text and text.strip() and text.strip() != "<br>":
                    final_result[name] = text
                    print(f"🟢 [AUTOFILL BULK] Datapoint '{name[:50]}' - has answer (length: {len(text)})")
                else:
                    # Return empty string to trigger upload UI in frontend
                    final_result[name] = ""
                    print(f"🟡 [AUTOFILL BULK] Datapoint '{name[:50]}' - no answer (text: {repr(text)}), returning empty string for upload UI")
            
            batch_with_answers = len([r for r in results if r[1] and r[1].strip() and r[1].strip() != "<br>"])
            batch_empty = len([r for r in results if not r[1] or not r[1].strip() or r[1].strip() == "<br>"])
            print(f"🔵 [AUTOFILL BULK] Batch {batch_num} completed - with_answers: {batch_with_answers}, empty: {batch_empty}")
            await asyncio.sleep(5)  # pause between batches to avoid rate limit

        print(f"🟢 [AUTOFILL BULK] generate_many COMPLETED - total results: {len(final_result)}, with_answers: {len([v for v in final_result.values() if v and v.strip()])}, empty: {len([v for v in final_result.values() if not v or not v.strip()])}")
        return final_result


class AiAutofillSearch:

    def __init__(self):
        self.timeout = 1800  # 30min
        self.indexer = indexer
        self.search_client = SearchIndexerClient(search_endpoint, AzureKeyCredential(search_key))

    def run_all_indexer(self):
        try:
            # Check if indexer is already running
            indexer_status = self.search_client.get_indexer_status(self.indexer)
            if indexer_status.status == "running":
                logger.info(f"Indexer {self.indexer} is already running, skipping invocation")
                # Wait for current run to complete
                for _n in range(self.timeout):
                    run_res = self.search_client.get_indexer_status(self.indexer)
                    if run_res.status != "running":
                        break
                    time.sleep(1)
                return
            
            # Indexer is not running, invoke it
            self.search_client.run_indexer(self.indexer)
            for _n in range(self.timeout):
                run_res = self.search_client.get_indexer_status(self.indexer)
                status = run_res.last_result.status
                if status == "success":
                    break
                time.sleep(1)
        except Exception as e:
            if "concurrent invocations are not allowed" in str(e) or "ResourceExistsError" in str(type(e).__name__):
                logger.warning(f"Indexer {self.indexer} is already running, skipping invocation: {e}")
                # Wait for current run to complete
                for _n in range(self.timeout):
                    try:
                        run_res = self.search_client.get_indexer_status(self.indexer)
                        if run_res.status != "running":
                            break
                    except Exception:
                        pass
                    time.sleep(1)
            else:
                logger.error(f"Error running indexer {self.indexer}: {e}", exc_info=True)
                raise


class AiAutofillStorageBlob:
    def __init__(self, container_name=None):
        self.blob_service_client = BlobServiceClient(
            azure_storage_blob_url,
            container_key,
        )
        self.container_name = container_name or settings.AUTOFILL_AI_AZURE_STORAGE_CONTAINER_NAME

    def generate_unique_filename(self, filename):
        import uuid
        base, ext = os.path.splitext(filename)
        unique_suffix = uuid.uuid4().hex
        return f"{base}_{unique_suffix}{ext}"

    def upload_blob_file(self, full_file_path, blob_name):
        container_client = self.blob_service_client.get_container_client(self.container_name)
        with open(full_file_path, "rb") as data:
            container_client.upload_blob(name=blob_name, data=data, overwrite=True)
    
    def generate_blob_sas_token(self, blob_name: str, expiry_hours: int = 1) -> str:
        """
        Generate Shared Access Signature (SAS) token for blob access.
        
        Args:
            blob_name: Blob name
            expiry_hours: Token expiry in hours (default: 1)
            
        Returns:
            SAS token string (without leading '?')
        """
        try:
            from datetime import datetime, timedelta
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas
            
            # Extract account name from URL
            # URL format: https://storageaccount.blob.core.windows.net/
            if hasattr(settings, 'AZURE_STORAGE_BLOB_NAME') and settings.AZURE_STORAGE_BLOB_NAME:
                account_name = settings.AZURE_STORAGE_BLOB_NAME
            else:
                # Extract from URL: https://storageaccount.blob.core.windows.net/
                url_without_protocol = azure_storage_blob_url.replace("https://", "").replace("http://", "")
                account_name = url_without_protocol.split(".")[0]
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=container_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
            )
            
            return sas_token
            
        except Exception as e:
            logger.warning(f"Failed to generate SAS token for {blob_name}: {e}")
            return ""

class AiAutofillVectorIndexer:
    def __init__(self, batch_size=16):
        """
        Initialize the indexer with a SearchClient and batch size.
        """
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=search_index_name,
            credential=AzureKeyCredential(search_key),
        )
        self.batch_size = batch_size

        # IMPORTANT: Make sure these field names exactly match your index schema.
        self.key_field_name = "chunk_id"           # Primary key field (`key=True`)
        self.content_field_name = "content"        # Field containing the document text
        self.vector_field_name = "contentVector"   # Field for vector embeddings
        self.flag_field_name = "is_vectorized"     # Boolean flag field (`filterable=True`)

    def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Create embeddings for a batch of text documents using Gemini.
        """
        gemini_client = get_gemini_client()
        embeddings = gemini_client.generate_embeddings(texts)
        return embeddings

    def update_vectors_for_unprocessed_docs(self):
        """
        Find documents that haven't been vectorized (based on the flag field),
        generate embeddings, and update them back to Azure Search in batches.
        """

        # Efficient and accurate filtering using the boolean flag field
        filter_query = f"{self.flag_field_name} eq false"

        try:
            results = self.search_client.search(
                search_text="",  # No keyword search
                filter=filter_query,
                select=[self.key_field_name, self.content_field_name],  # Only fetch necessary fields
            )
            documents_to_process = list(results)
        except Exception:
            return

        total_docs = len(documents_to_process)
        if total_docs == 0:
            return


        for i in range(0, total_docs, self.batch_size):
            batch = documents_to_process[i:i + self.batch_size]
            i // self.batch_size + 1
            (total_docs + self.batch_size - 1) // self.batch_size

            texts_to_embed = [
                doc[self.content_field_name]
                for doc in batch
                if doc.get(self.content_field_name)
            ]

            if not texts_to_embed:
                continue

            try:
                # 1. Create embeddings for the entire batch
                embeddings = self.create_embeddings_batch(texts_to_embed)

                documents_to_upload = []
                for doc, vector in zip(batch, embeddings, strict=False):
                    # 2. Prepare updated document with key, new vector, and updated flag
                    updated_doc = {
                        self.key_field_name: doc[self.key_field_name],
                        self.vector_field_name: vector,
                        self.flag_field_name: True,  # Mark as processed
                    }
                    documents_to_upload.append(updated_doc)

                # 3. Upload the updated batch to Azure Search
                result = self.search_client.merge_or_upload_documents(documents=documents_to_upload)

                successful_uploads = sum(1 for r in result if r.succeeded)
                if successful_uploads < len(batch):
                    for r in result:
                        if not r.succeeded:
                            pass

            except Exception as e:
                logger.warning(f"Exception occurred: {e}")


class AutofillRagChat:
    """RAG Chat agent for Autofill using Azure OpenAI with Azure AI Search"""
    
    def __init__(self):
        self.question = ""
        self.company_id = None
        self.company_id_field = "company_id"  # Field name in Azure AI Search index
        
        # Initialize search client
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=search_index_name,
            credential=AzureKeyCredential(search_key),
        )
    
    def chat(
        self,
        question: str,
        company_id: int,
        original_text: Optional[str] = None,
        field_type: Optional[str] = None,
        field_options: Optional[List[str]] = None,
    ) -> Tuple[str, Optional[List], Optional[List]]:
        """
        Chat with Autofill RAG system using Gemini.

        Args:
            question: User's question (datapoint name/question)
            company_id: Company ID for filtering
            original_text: Original text from datapoint (optional)
            field_type: Type of form field (for structured prompts)
            field_options: Options for select/radio/checkbox fields

        Returns:
            Tuple of (answer, references, retrieved_chunks)
            retrieved_chunks: List of dicts with {"id": chunk_id, "score": relevance_score}
        """
        try:
            self.question = question
            self.company_id = company_id
            
            # Build enhanced question with original_text if available
            enhanced_question = question
            if original_text and original_text.strip():
                enhanced_question = f"{question}\n\nContext: {original_text}"

            # Build FormField if field_type is provided for structured prompts
            form_field = None
            if field_type:
                try:
                    ft = FieldType(field_type) if isinstance(field_type, str) else field_type
                    form_field = FormField(
                        name=question,
                        field_type=ft,
                        options=field_options or [],
                    )
                except Exception as e:
                    logger.warning(f"Failed to create FormField: {e}")

            # Build filter for company-specific documents
            filter_query = f"{self.company_id_field} eq {company_id}" if company_id else None
            
            # Check if there are documents in the index first
            print(f"🔵 [AUTOFILL RAG] Checking index '{search_index_name}' for documents with filter: {filter_query}")
            logger.info(f"DEBUG: Autofill RAG - Checking index '{search_index_name}' for documents with filter: {filter_query}")
            try:
                # Quick check: count documents in index
                count_results = self.search_client.search(
                    search_text="*",
                    filter=filter_query,
                    select=["chunk_id"],
                    top=1,
                )
                doc_count = len(list(count_results))
                print(f"🔵 [AUTOFILL RAG] Found {doc_count} documents in index with filter: {filter_query}")
                logger.info(f"DEBUG: Autofill RAG - Found {doc_count} documents in index with filter: {filter_query}")
                
                if doc_count == 0:
                    print(f"🟡 [AUTOFILL RAG] ⚠️ No documents found - returning empty string for upload UI")
                    logger.warning(f"DEBUG: Autofill RAG - ⚠️ No documents found in index '{search_index_name}' with filter: {filter_query}")
                    # Return empty string to trigger upload UI in frontend
                    return "", [], []
            except Exception as e:
                print(f"🔴 [AUTOFILL RAG] Error checking index: {e} - returning empty string for upload UI")
                logger.error(f"DEBUG: Autofill RAG - Error checking index: {e}", exc_info=True)
                # Return empty string on error to trigger upload UI
                return "", [], []
            
            # ============================================================
            # STEP 4: PROMPT CONSTRUCTION
            # ============================================================
            logger.info(f"[AUTOFILL RAG] =========================================")
            logger.info(f"[AUTOFILL RAG] STEP 4: PROMPT CONSTRUCTION")
            logger.info(f"[AUTOFILL RAG] Goal: Force the LLM to answer using only provided context")
            logger.info(f"[AUTOFILL RAG] Method: System prompt + User question + Retrieved context")
            
            # Retrieve relevant chunks using Gemini embeddings + Azure AI Search
            # Step 1: Generate query embedding with Gemini
            gemini_client = get_gemini_client()
            query_embedding = gemini_client.generate_query_embedding(enhanced_question)
            logger.info(f"[AUTOFILL RAG] Generated query embedding with Gemini, dimension: {len(query_embedding)}")

            # Step 2: Vector search in Azure AI Search
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=30,
                fields="contentVector",
            )

            search_client = SearchClient(
                endpoint=search_endpoint,
                index_name=search_index_name,
                credential=AzureKeyCredential(search_key),
            )

            search_results = search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_query,
                select=["file_name", "blob_name", "chunk_id", "chunk_index", "content"],
                top=30,
            )

            search_results_list = list(search_results)
            logger.info(f"[AUTOFILL RAG] Vector search returned {len(search_results_list)} documents")

            if not search_results_list:
                logger.warning(f"[AUTOFILL RAG] No documents found in search")
                return "", [], []

            # Step 3: Extract content from top results
            retrieved_contents = []
            for result in search_results_list[:5]:  # Use top 5 for context
                content = result.get("content", "")
                if content:
                    retrieved_contents.append(content)

            if not retrieved_contents:
                logger.warning(f"[AUTOFILL RAG] No content in search results")
                return "", [], []

            document_context = "\n\n".join(retrieved_contents[:5])  # Combine top 5 chunks
            
            logger.info(f"[AUTOFILL RAG] Step 4: System prompt constructed (precise document analyzer)")
            logger.info(f"[AUTOFILL RAG] Step 4: User question: {question[:100]}...")
            logger.info(f"[AUTOFILL RAG] Step 4: ✅ Prompt construction completed")
            
            # ============================================================
            # STEP 5: ANSWER GENERATION (CROSS-ATTENTION LEVEL 2)
            # ============================================================
            logger.info(f"[AUTOFILL RAG] =========================================")
            logger.info(f"[AUTOFILL RAG] STEP 5: ANSWER GENERATION (CROSS-ATTENTION LEVEL 2)")
            logger.info(f"[AUTOFILL RAG] Goal: Generate answer grounded in retrieved documents")
            logger.info(f"[AUTOFILL RAG] Method: Azure OpenAI GPT with cross-attention to context")
            logger.info(f"[AUTOFILL RAG] Model: {deployment_id}")
            logger.info(f"[AUTOFILL RAG] Step 5: Starting LLM generation with Gemini...")

            # Step 4: Build prompt based on field type
            if form_field:
                prompt = FormAnalyzer.build_structured_prompt(
                    field=form_field,
                    document_context=document_context,
                    original_question=original_text,
                )
            else:
                # Default text field prompt
                prompt = self._make_autofill_question(enhanced_question, original_text, document_context)

            logger.info(f"DEBUG: Autofill RAG - Calling Gemini for generation")
            print(f"🔵 [AUTOFILL RAG] Calling Gemini for generation")

            # Call Gemini for answer generation
            try:
                answer = gemini_client.generate_content(
                    prompt=prompt,
                    temperature=0.1,
                    max_output_tokens=8192,
                )

                logger.info(f"[AUTOFILL RAG] Step 5: LLM response received from Gemini")

            except Exception as e:
                logger.error(f"Error calling Gemini: {e}", exc_info=True)
                print(f"🔴 [AUTOFILL RAG] Error calling Gemini: {e}")
                return "", [], []
            
            # Process Gemini response
            print(f"🔵 [AUTOFILL RAG] Processing Gemini answer...")
            print(f"🔵 [AUTOFILL RAG] Answer extracted - length: {len(answer) if answer else 0}, has_content: {bool(answer and answer.strip())}")
            print(f"📄 [AUTOFILL RAG] AI Response (first 500 chars): {answer[:500] if answer else 'EMPTY'}")

            # If answer is empty or contains "no information" messages, return empty string
            if not answer or not answer.strip():
                print(f"🟡 [AUTOFILL RAG] Empty answer - returning empty string for upload UI")
                logger.info("DEBUG: Autofill RAG - Empty answer, returning empty string for upload UI")
                return "", [], []

            # Check for "no information" indicators
            no_info_indicators = [
                "Please try another query or topic",
                "This information is not specified",
                "not specified in the available documents",
                "not available in the documents",
                "not specified in the documents",
            ]
            if any(indicator.lower() in answer.lower() for indicator in no_info_indicators):
                print(f"🟡 [AUTOFILL RAG] No information indicator found - returning empty string for upload UI")
                print(f"📄 [AUTOFILL RAG] Answer content that triggered no-info: {answer[:200]}")
                logger.info("DEBUG: Autofill RAG - No information found, returning empty string for upload UI")
                return "", [], []

            print(f"🟢 [AUTOFILL RAG] Valid answer found - length: {len(answer)}")
            print(f"📄 [AUTOFILL RAG] Full AI Response:\n{answer}\n")

            # Extract references from search results
            references = []
            retrieved_chunks = []
            seen_files = set()

            for idx, result in enumerate(search_results_list[:5]):
                file_name = result.get("file_name", "")
                blob_name = result.get("blob_name", "")
                chunk_id = result.get("chunk_id", "")
                chunk_index = result.get("chunk_index", 0)
                score = getattr(result, '@search.score', 0.0) or result.get('@search.score', 0.0)

                # Add to retrieved_chunks
                if chunk_id:
                    retrieved_chunks.append({
                        "id": chunk_id,
                        "score": float(score) if score else 0.0,
                        "chunk_index": chunk_index,
                    })

                # Add unique file reference
                if blob_name and file_name:
                    file_key = (blob_name, file_name)
                    if file_key not in seen_files:
                        seen_files.add(file_key)
                        references.append({
                            "blob_name": blob_name,
                            "file_name": file_name,
                        })

            logger.info(f"DEBUG: Autofill RAG - Created {len(references)} references from search results")
            logger.info(f"DEBUG: Autofill RAG - Retrieved {len(retrieved_chunks)} chunks with scores")

            # Clean document references from answer
            answer = re.sub(r"\[doc\d+\]", "", answer)

            logger.info(f"[AUTOFILL RAG] Step 5: ✅ Answer generation completed with Gemini")
            logger.info(f"[AUTOFILL RAG] Step 5: Answer length: {len(answer)} characters")
            logger.info(f"[AUTOFILL RAG] Step 5: References extracted: {len(references)}")
            logger.info(f"[AUTOFILL RAG] =========================================")
            logger.info(f"[AUTOFILL RAG] ✅ RAG FLOW COMPLETED with Gemini")

            print(f"🟢 [AUTOFILL RAG] Returning valid answer - length: {len(answer)}, references: {len(references)}, chunks: {len(retrieved_chunks)}")
            return answer, references, retrieved_chunks
            
        except Exception as e:
            print(f"🔴 [AUTOFILL RAG] Exception occurred: {e} - returning empty string for upload UI")
            logger.error(f"Error in Autofill RAG chat: {e}", exc_info=True)
            # Return empty string on error to trigger upload UI in frontend
            return "", [], []
    
    def _make_autofill_question(
        self,
        query: str,
        original_text: Optional[str] = None,
        document_context: Optional[str] = None,
    ) -> str:
        """Constructs the question to be asked based on the provided query."""
        question = f"""Based EXCLUSIVELY on the provided document context, analyze and respond to the following question:

Question: {query}

"""
        if document_context:
            question += f"""Document Context:
{document_context}

"""

        question += """CRITICAL INSTRUCTIONS:
- Use ONLY information explicitly stated in the provided document context
- Quote exact figures, percentages, dates, and statistics from the documents
- Reference specific document sections, pages, or chapters when available
- Use the document's exact terminology and technical language

IMPORTANT INTERPRETATION NOTE:
- If any question is related to biodiversity-sensitive areas, clearly state whether the company reports **no material impacts** due to mitigation or restoration measures.
- Use direct quotes when available
- Always include specific numbers, buffer zones, and tools/frameworks used when available

REQUIRED RESPONSE FORMAT: Valid HTML
- Use `<ul>`, `<li>`, `<b>`, `<p>`, `<blockquote>` tags
- Create 4-8 bullet points with specific information from documents
- Include direct quotes using `<blockquote>` tags
- Use `<b>` tags for exact numbers, percentages, and key terms from documents

CONTENT REQUIREMENTS:
- What specific data, statistics, or metrics are mentioned in the documents?
- What exact methodologies, tools, or frameworks are explicitly named?
- What precise dates, timeframes, or periods are specified?
- What specific findings or results are stated in the documents?
- Are there direct quotes from stakeholders or experts mentioned?
- What exact limitations, challenges, or gaps are explicitly stated?

IF NO RELEVANT INFORMATION AVAILABLE:
Return exactly: "Not specified in the documents"

Please provide a response based STRICTLY on the available document content.
"""
        return question.strip()
    
    def _get_references_from_citations(
        self,
        citations: List,
        question: str,
        company_id: int,
        filter_query: Optional[str] = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get references from top documents (same as Azure OpenAI queried).
        
        Args:
            citations: Citations from Azure OpenAI
            question: Original question
            company_id: Company ID
            filter_query: Filter query string
            
        Returns:
            Tuple of (references, retrieved_chunks)
            references: List of references with blob_name and file_name
            retrieved_chunks: List of dicts with {"id": chunk_id, "score": relevance_score}
        """
        if not citations:
            logger.warning("DEBUG: Autofill RAG - No citations provided, returning empty references")
            return [], []
        
        try:
            logger.debug(f"DEBUG: Autofill RAG - Getting references, citations count: {len(citations)}")
            
            # Create embedding for question (same as Azure OpenAI used)
            client = get_autofill_client()
            embedding_response = client.embeddings.create(
                model=EMBEDDING_DEPLOYMENT_ID,
                input=[question],
                dimensions=EMBEDDING_DIMENSIONS,  # Specify 256 dimensions - CRITICAL!
            )
            query_embedding = embedding_response.data[0].embedding
            # Verify dimension
            actual_dim = len(query_embedding)
            if actual_dim != EMBEDDING_DIMENSIONS:
                logger.error(f"❌ Embedding dimension mismatch! Expected {EMBEDDING_DIMENSIONS}, got {actual_dim}")
                raise ValueError(f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {actual_dim}")
            logger.debug(f"DEBUG: Autofill RAG - Created query embedding, dimension: {len(query_embedding)}")
            
            # STEP 1: Fast Retrieval (NO CROSS-ATTENTION)
            # Retrieve many candidate chunks quickly (top 20-50)
            # This is fast but not deeply accurate - uses cosine similarity only
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=30,  # Retrieve 30-50 candidates for reranking (as per RAG flow)
                fields="contentVector",
            )
            
            logger.info(f"[AUTOFILL RAG] Step 1: Fast Retrieval - Vector search with filter: {filter_query}")
            
            # Query Azure AI Search - retrieve more chunks for reranking
            search_results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_query,
                select=["file_name", "blob_name", "chunk_id", "chunk_index", "content"],  # Include content for reranking
                top=30,  # Retrieve top 30-50 for reranking (as per RAG flow)
            )
            
            # Convert to list to check results
            search_results_list = list(search_results)
            logger.info(f"[AUTOFILL RAG] Step 1: Fast Retrieval - Vector search returned {len(search_results_list)} documents")
            
            if not search_results_list:
                logger.warning(f"[AUTOFILL RAG] No documents found in Azure AI Search for question: {question[:50]}... with filter: {filter_query}")
                return [], []
            
            # STEP 2: Metadata / Entity Filtering
            # Filter by metadata (company_id) - already done via filter_query
            # Remaining chunks: ~10-20 (after filtering)
            chunks_for_reranking = []
            for result in search_results_list:
                chunk_content = result.get("content", "")
                if not chunk_content:
                    continue
                
                chunk_data = {
                    "content": chunk_content,
                    "file_name": result.get("file_name", ""),
                    "blob_name": result.get("blob_name", ""),
                    "chunk_id": result.get("chunk_id", ""),
                    "chunk_index": result.get("chunk_index", 0),
                    "vector_score": getattr(result, '@search.score', None) or result.get('@search.score', None) or 0.0,
                }
                chunks_for_reranking.append(chunk_data)
            
            # STEP 3: Re-ranking (CROSS-ATTENTION LEVEL 1)
            # Let the query read each chunk and score relevance
            # Keep top 3-5 chunks after reranking
            try:
                from companies.sdk.rag_reranker import rerank_chunks
                
                logger.info(f"[AUTOFILL RAG] Step 3: Reranking {len(chunks_for_reranking)} chunks with Cross-Encoder...")
                top_chunks, all_ranked_chunks = rerank_chunks(
                    query=question,
                    chunks=chunks_for_reranking,
                    top_k=5,  # Get top 3-5 as per RAG flow
                    content_field="content",
                )
                
                # Log reranking results safely
                if top_chunks:
                    top1_score = top_chunks[0].get('rerank_score', 0.0) if top_chunks else 0.0
                    top3_score = top_chunks[2].get('rerank_score', 0.0) if len(top_chunks) > 2 else 0.0
                    top5_score = top_chunks[4].get('rerank_score', 0.0) if len(top_chunks) > 4 else 0.0
                    logger.info(f"[AUTOFILL RAG] Step 3: ✅ Reranking completed - top 1 score: {top1_score:.4f}, top 3 score: {top3_score:.4f}, top 5 score: {top5_score:.4f}")
                else:
                    logger.info(f"[AUTOFILL RAG] Step 3: ✅ Reranking completed - no chunks returned")
                
                # Use reranked chunks (top 3-5) for references
                ranked_results = top_chunks if top_chunks else chunks_for_reranking[:5]
            except Exception as rerank_exc:
                logger.warning(f"[AUTOFILL RAG] Step 3: ⚠️ Reranking failed: {rerank_exc}, using original vector search results")
                logger.exception(rerank_exc)
                # Fallback: use original vector search results (top 5)
                ranked_results = chunks_for_reranking[:5]
            
            # STEP 4: Extract references and retrieved_chunks from top-ranked results
            seen_files = set()
            references = []
            retrieved_chunks = []
            
            for result in ranked_results:
                file_name = result.get("file_name", "")
                blob_name = result.get("blob_name", "")
                chunk_id = result.get("chunk_id", "")
                chunk_index = result.get("chunk_index", 0)
                
                # Get relevance score (prefer rerank_score, fallback to vector_score)
                score = result.get('rerank_score') or result.get('vector_score', 0.0)
                
                # Add to retrieved_chunks
                if chunk_id:
                    retrieved_chunks.append({
                        "id": chunk_id,
                        "score": score,
                        "chunk_index": chunk_index,
                    })
                
                # Add unique file reference
                if blob_name and file_name:
                    file_key = (blob_name, file_name)
                    if file_key not in seen_files:
                        seen_files.add(file_key)
                        references.append({
                            "blob_name": blob_name,
                            "file_name": file_name,
                        })
            
            logger.info(f"DEBUG: Autofill RAG - Created {len(references)} unique references and {len(retrieved_chunks)} retrieved chunks")
            return references, retrieved_chunks
            
        except Exception as e:
            logger.error(f"Error getting references from citations: {e}", exc_info=True)
            return [], []

