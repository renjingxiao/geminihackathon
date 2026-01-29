"""
Lisa RAG SDK - Azure AI Search Vector RAG Implementation for Gap Analysis
Uses Azure Document Intelligence (Layout) for document analysis
Uses Google Gemini for embeddings and chat
Uses AUTOFILL_AI infrastructure (container, search, storage)
"""
import logging
import os
import re
import uuid
from typing import List, Optional, Dict, Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.storage.blob import BlobServiceClient
from django.conf import settings

# Import Gemini client
try:
    from autofill.gemini_client import get_gemini_client, EMBEDDING_DIMENSIONS
except ImportError:
    # When running directly in autofill directory
    from gemini_client import get_gemini_client, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
except ImportError:
    DocumentIntelligenceClient = None
    logger.warning("azure-ai-documentintelligence not installed. Install with: pip install azure-ai-documentintelligence")

# Azure AI Search Setup for Lisa RAG (uses AUTOFILL_AI settings)
LISA_RAG_SEARCH_ENDPOINT = getattr(settings, 'AUTOFILL_AI_AZURE_AI_SEARCH_ENDPOINT', '')
LISA_RAG_SEARCH_KEY = getattr(settings, 'AUTOFILL_AI_AZURE_AI_SEARCH_KEY', '')
LISA_RAG_SEARCH_INDEX_NAME = getattr(settings, 'AUTOFILL_AI_AZURE_AI_SEARCH_INDEX_NAME', 'aiautofill-index')

# Gemini embedding dimensions (768 for embedding-001)
# NOTE: Azure AI Search index must be configured to support 768-dimensional vectors

# Azure Storage Blob Setup for Lisa RAG (uses AUTOFILL_AI container)
LISA_RAG_STORAGE_CONTAINER_NAME = getattr(settings, 'AUTOFILL_AI_AZURE_STORAGE_CONTAINER_NAME', 'ai-autofill-regulation-biodiversity-storage')
LISA_RAG_STORAGE_BLOB_URL = getattr(settings, 'AUTOFILL_AI_AZURE_STORAGE_BLOB_URL', settings.AZURE_STORAGE_BLOB_URL)
LISA_RAG_STORAGE_CONTAINER_KEY = getattr(settings, 'AUTOFILL_AI_AZURE_STORAGE_CONTAINER_KEY', settings.AZURE_STORAGE_CONTAINER_KEY)

# Azure Document Intelligence Setup (uses same as Justine or can be separate)
LISA_RAG_DOCUMENT_INTELLIGENCE_ENDPOINT = getattr(settings, 'RAG_DOCUMENT_INTELLIGENCE_ENDPOINT', '')
LISA_RAG_DOCUMENT_INTELLIGENCE_KEY = getattr(settings, 'RAG_DOCUMENT_INTELLIGENCE_KEY', '')
LISA_RAG_DOCUMENT_INTELLIGENCE_MODEL = getattr(settings, 'RAG_DOCUMENT_INTELLIGENCE_MODEL', 'prebuilt-layout')  # prebuilt-layout for general documents

# Chunking configuration
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks


# Note: Gemini client is now provided by gemini_client.py via get_gemini_client()


class LisaRagDocumentIntelligence:
    """Azure Document Intelligence client for analyzing documents"""
    
    def __init__(self):
        """Initialize Azure Document Intelligence client"""
        if DocumentIntelligenceClient is None:
            raise ImportError("azure-ai-documentintelligence package is required. Install with: pip install azure-ai-documentintelligence")
        
        if not LISA_RAG_DOCUMENT_INTELLIGENCE_ENDPOINT or not LISA_RAG_DOCUMENT_INTELLIGENCE_KEY:
            raise ValueError("LISA_RAG_DOCUMENT_INTELLIGENCE_ENDPOINT and LISA_RAG_DOCUMENT_INTELLIGENCE_KEY must be set in settings")
        
        self.client = DocumentIntelligenceClient(
            endpoint=LISA_RAG_DOCUMENT_INTELLIGENCE_ENDPOINT,
            credential=AzureKeyCredential(LISA_RAG_DOCUMENT_INTELLIGENCE_KEY),
        )
        self.model_id = LISA_RAG_DOCUMENT_INTELLIGENCE_MODEL
    
    def analyze_document(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze document using Azure Document Intelligence Layout model.
        
        Args:
            file_path: Path to document file (PDF, image, etc.)
            
        Returns:
            Dictionary with structured document data
        """
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            # Analyze document with prebuilt-layout model
            poller = self.client.begin_analyze_document(
                model_id=self.model_id,  # "prebuilt-layout"
                body=file_data,
                content_type="application/octet-stream",
            )
            
            result = poller.result()
            
            # Extract structured data
            structured_data = {
                "content": result.content if hasattr(result, 'content') else "",
                "pages": [],
                "tables": [],
                "key_value_pairs": {},
            }
            
            if hasattr(result, 'pages'):
                for page in result.pages:
                    structured_data["pages"].append({
                        "page_number": page.page_number if hasattr(page, 'page_number') else None,
                        "width": page.width if hasattr(page, 'width') else None,
                        "height": page.height if hasattr(page, 'height') else None,
                    })
            
            if hasattr(result, 'tables'):
                for table in result.tables:
                    table_data = {
                        "row_count": table.row_count if hasattr(table, 'row_count') else 0,
                        "column_count": table.column_count if hasattr(table, 'column_count') else 0,
                    }
                    structured_data["tables"].append(table_data)
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error analyzing document: {e}", exc_info=True)
            raise
    
    def format_structured_content(self, structured_data: Dict[str, Any]) -> str:
        """
        Format structured data from Document Intelligence into text for chunking.
        
        Args:
            structured_data: Dictionary with structured document data
            
        Returns:
            Formatted text string
        """
        text_parts = []
        
        # Add main content
        content = structured_data.get("content", "")
        if content:
            text_parts.append(content)
        
        # Add tables information
        tables = structured_data.get("tables", [])
        if tables:
            text_parts.append(f"\n\nTables found: {len(tables)}")
            for idx, table in enumerate(tables, 1):
                row_count = table.get("row_count", 0)
                column_count = table.get("column_count", 0)
                text_parts.append(f"Table {idx}: {row_count} rows x {column_count} columns")
        
        formatted_text = "\n".join(text_parts)
        
        if not formatted_text or not formatted_text.strip():
            # Fallback: use page content if available
            logger.warning("No formatted text from structured data, using raw content")
            formatted_text = content if content else ""
        
        return formatted_text.strip()


class LisaRagTextChunker:
    """Text chunker for Lisa RAG"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []
        
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        
        chunks = []
        text_length = len(text)
        start = 0
        max_iterations = (text_length // self.chunk_size) + 10  # Safety limit
        
        iteration = 0
        while start < text_length and iteration < max_iterations:
            iteration += 1
            end = min(start + self.chunk_size, text_length)
            chunk = text[start:end]
            chunk_stripped = chunk.strip()
            
            if chunk_stripped:  # Only append non-empty chunks
                chunks.append(chunk_stripped)
            
            # Move start forward (with overlap)
            if end >= text_length:
                break
            start = end - self.chunk_overlap
            if start <= 0:
                start = end
        
        if not chunks:
            # Fallback: return entire text as single chunk
            logger.warning("No chunks created, returning entire text as single chunk")
            chunks = [text.strip()] if text.strip() else []
        
        return chunks


class LisaRagStorageBlob:
    """Azure Blob Storage client for Lisa RAG"""
    
    def __init__(self):
        self.blob_service_client = BlobServiceClient(
            account_url=LISA_RAG_STORAGE_BLOB_URL,
            credential=LISA_RAG_STORAGE_CONTAINER_KEY,
        )
        self.container_name = LISA_RAG_STORAGE_CONTAINER_NAME
    
    def upload_file(self, file_path: str, blob_name: str) -> str:
        """
        Upload file to Azure Blob Storage.
        
        Args:
            file_path: Local file path
            blob_name: Blob name (path) in storage
            
        Returns:
            Blob name (same as input)
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            with open(file_path, "rb") as data:
                container_client.upload_blob(name=blob_name, data=data, overwrite=True)
            
            logger.info(f"Uploaded file to blob: {blob_name}")
            return blob_name
            
        except Exception as e:
            logger.error(f"Error uploading file to blob: {e}", exc_info=True)
            raise
    
    def download_blob_content(self, blob_name: str) -> bytes:
        """Download blob content as bytes"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            return blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Error downloading blob {blob_name}: {e}", exc_info=True)
            raise
    
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
            
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=LISA_RAG_STORAGE_BLOB_URL.split("//")[1].split(".")[0],
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=LISA_RAG_STORAGE_CONTAINER_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
            )
            
            return sas_token
            
        except Exception as e:
            logger.warning(f"Failed to generate SAS token for {blob_name}: {e}")
            return ""


class LisaRagVectorIndexer:
    """Vector indexer for Lisa RAG - handles embedding generation and indexing"""
    
    def __init__(self, batch_size: int = 16):
        """
        Initialize the vector indexer.
        
        Args:
            batch_size: Number of documents to process in each batch
        """
        # Log configuration for debugging
        logger.info(f"Initializing LisaRagVectorIndexer:")
        logger.info(f"  - Endpoint: {LISA_RAG_SEARCH_ENDPOINT}")
        logger.info(f"  - Index Name: {LISA_RAG_SEARCH_INDEX_NAME}")
        logger.info(f"  - Key present: {'Yes' if LISA_RAG_SEARCH_KEY else 'No'}")
        
        if not LISA_RAG_SEARCH_ENDPOINT:
            logger.error("❌ LISA_RAG_SEARCH_ENDPOINT is empty! Check AUTOFILL_AI_AZURE_AI_SEARCH_ENDPOINT setting.")
        if not LISA_RAG_SEARCH_KEY:
            logger.error("❌ LISA_RAG_SEARCH_KEY is empty! Check AUTOFILL_AI_AZURE_AI_SEARCH_KEY setting.")
        if not LISA_RAG_SEARCH_INDEX_NAME:
            logger.error("❌ LISA_RAG_SEARCH_INDEX_NAME is empty! Check AUTOFILL_AI_AZURE_AI_SEARCH_INDEX_NAME setting.")
        
        self.search_client = SearchClient(
            endpoint=LISA_RAG_SEARCH_ENDPOINT,
            index_name=LISA_RAG_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(LISA_RAG_SEARCH_KEY),
        )
        self.batch_size = batch_size
        
        # Field names matching Azure AI Search index schema
        self.key_field_name = "chunk_id"  # Primary key
        self.content_field_name = "content"  # Text content
        self.vector_field_name = "contentVector"  # Vector embeddings
        self.file_name_field = "file_name"  # Original file name
        self.company_id_field = "company_id"  # Company ID
        self.blob_name_field = "blob_name"  # Blob storage path
        self.chunk_index_field = "chunk_index"  # Index of chunk in file
        self.is_vectorized_field = "is_vectorized"  # Boolean flag
    
    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a batch of texts using Gemini embedding-001.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each 768 dimensions)
        """
        gemini_client = get_gemini_client()
        embeddings = gemini_client.generate_embeddings(texts)

        logger.debug(f"✅ Generated {len(embeddings)} embeddings with dimension {EMBEDDING_DIMENSIONS}")
        return embeddings
    
    def index_document_chunks(
        self,
        chunks: List[str],
        file_name: str,
        blob_name: str,
        company_id: Optional[int] = None,
    ) -> int:
        """
        Index document chunks with embeddings into Azure AI Search.
        
        Args:
            chunks: List of text chunks
            file_name: Original file name
            blob_name: Blob storage path (required for chunk_id generation)
            company_id: Company ID (optional, used for filtering only)
            
        Returns:
            Number of chunks indexed
        """
        if not chunks:
            logger.warning("No chunks provided for indexing")
            return 0
        
        if not blob_name:
            logger.error("blob_name is required for chunk_id generation")
            return 0
        
        # Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        embeddings = self.create_embeddings_batch(chunks)
        
        # Prepare documents for indexing
        documents = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create unique chunk_id using blob_name and index
            import hashlib
            blob_hash = hashlib.md5(blob_name.encode()).hexdigest()[:8]
            chunk_id = f"{blob_hash}_{idx}"
            
            doc = {
                self.key_field_name: chunk_id,
                self.content_field_name: chunk,
                self.vector_field_name: embedding,
                self.file_name_field: file_name,
                self.blob_name_field: blob_name,
                self.chunk_index_field: idx,
                self.is_vectorized_field: True,
            }
            
            # Add company_id only if provided (for filtering)
            if company_id is not None:
                doc[self.company_id_field] = company_id
            
            documents.append(doc)
        
        # Upload documents in batches
        total_indexed = 0
        logger.info(f"Starting to index {len(documents)} documents to index '{LISA_RAG_SEARCH_INDEX_NAME}' at endpoint '{LISA_RAG_SEARCH_ENDPOINT}'")
        
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            try:
                logger.debug(f"Uploading batch {i//self.batch_size + 1} with {len(batch)} documents...")
                result = self.search_client.upload_documents(documents=batch)
                
                # Check each result
                successful = 0
                failed = 0
                for r in result:
                    if r.succeeded:
                        successful += 1
                    else:
                        failed += 1
                        logger.error(f"Failed to index document {r.key}: {r.error_message}")
                
                total_indexed += successful
                logger.info(f"Indexed {successful}/{len(batch)} documents in batch (failed: {failed})")
                
            except Exception as e:
                logger.error(f"Error indexing batch: {e}", exc_info=True)
                logger.error(f"Batch details: first doc keys: {[doc.get(self.key_field_name) for doc in batch[:3]]}")
        
        logger.info(f"Total indexed: {total_indexed}/{len(chunks)} chunks for file '{file_name}'")
        if total_indexed < len(chunks):
            logger.warning(f"⚠️ Only indexed {total_indexed}/{len(chunks)} chunks. Some documents may have failed.")
        
        return total_indexed


class LisaRagDocumentProcessor:
    """
    Complete document processing pipeline for Lisa RAG:
    Document Intelligence → Chunking → Embedding → Indexing
    """
    
    def __init__(self):
        self.doc_intelligence = LisaRagDocumentIntelligence()
        self.chunker = LisaRagTextChunker()
        self.indexer = LisaRagVectorIndexer()
        self.storage = LisaRagStorageBlob()
    
    def process_and_index_document_with_blob(
        self,
        file_path: str,
        file_name: str,
        company_id: int,
        blob_name: str,
    ) -> int:
        """
        Complete pipeline: Document Intelligence → Chunking → Embedding → Indexing
        (Uses existing blob_name, skips upload step)
        
        Args:
            file_path: Local file path (for Document Intelligence only)
            file_name: Original file name
            company_id: Company ID
            blob_name: Existing blob name (file already uploaded)
            
        Returns:
            Number of chunks indexed
        """
        try:
            # Step 1: Analyze with Azure Document Intelligence
            logger.info(f"Analyzing document with Document Intelligence: {file_name} (model: prebuilt-layout)")
            structured_data = self.doc_intelligence.analyze_document(file_path)
            
            # Step 2: Format structured content to text
            logger.info(f"Formatting structured content to text...")
            formatted_text = self.doc_intelligence.format_structured_content(structured_data)
            
            if not formatted_text or not formatted_text.strip():
                logger.warning(f"No content extracted from {file_name}")
                return 0
            
            logger.info(f"Formatted text length: {len(formatted_text)} characters")
            
            # Step 3: Skip upload (file already uploaded, use provided blob_name)
            logger.info(f"Using existing blob: {blob_name} (file already uploaded)")
            
            # Step 4: Chunking
            logger.info(f"Chunking text into chunks (chunk_size={self.chunker.chunk_size}, overlap={self.chunker.chunk_overlap})...")
            try:
                chunks = self.chunker.chunk_text(formatted_text)
                logger.info(f"Created {len(chunks)} chunks")
                
                if not chunks:
                    logger.warning(f"No chunks created from text")
                    return 0
                
            except Exception as e:
                logger.error(f"Error during chunking: {e}", exc_info=True)
                return 0
            
            # Step 5: Index with embeddings
            logger.info(f"Indexing {len(chunks)} chunks with embeddings...")
            indexed_count = self.indexer.index_document_chunks(
                chunks=chunks,
                file_name=file_name,
                blob_name=blob_name,
                company_id=company_id,
            )
            
            logger.info(f"Successfully indexed {indexed_count} chunks for {file_name}")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Error processing document {file_name}: {e}", exc_info=True)
            return 0


class LisaRagChat:
    """Chat agent for Lisa RAG using Azure OpenAI with Azure AI Search"""
    
    def __init__(self):
        self.question = ""
        self.company_id = None
        self.company_id_field = "company_id"  # Field name in Azure AI Search index
        
        # Initialize search client
        self.search_client = SearchClient(
            endpoint=LISA_RAG_SEARCH_ENDPOINT,
            index_name=LISA_RAG_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(LISA_RAG_SEARCH_KEY),
        )
    
    def chat(self, question: str, company_id: int) -> tuple[str, Optional[List], Optional[List]]:
        """
        Chat with Lisa RAG system.
        
        Args:
            question: User's question
            company_id: Company ID for filtering
            
        Returns:
            Tuple of (answer, references, retrieved_chunks)
            retrieved_chunks: List of dicts with {"id": chunk_id, "score": relevance_score}
        """
        try:
            self.question = question
            self.company_id = company_id
            
            # Build filter for company-specific documents
            filter_query = f"{self.company_id_field} eq {company_id}" if company_id else None
            
            # Check if there are documents in the index first
            logger.info(f"DEBUG: Lisa RAG - Checking index '{LISA_RAG_SEARCH_INDEX_NAME}' for documents with filter: {filter_query}")
            try:
                # Quick check: count documents in index
                count_results = self.search_client.search(
                    search_text="*",
                    filter=filter_query,
                    select=["chunk_id"],
                    top=1,
                )
                doc_count = len(list(count_results))
                logger.info(f"DEBUG: Lisa RAG - Found {doc_count} documents in index with filter: {filter_query}")
                
                if doc_count == 0:
                    logger.warning(f"DEBUG: Lisa RAG - ⚠️ No documents found in index '{LISA_RAG_SEARCH_INDEX_NAME}' with filter: {filter_query}")
                    logger.warning(f"DEBUG: Lisa RAG - Index endpoint: {LISA_RAG_SEARCH_ENDPOINT}")
                    logger.warning(f"DEBUG: Lisa RAG - This may be why Azure OpenAI returns no citations")
            except Exception as e:
                logger.error(f"DEBUG: Lisa RAG - Error checking index: {e}", exc_info=True)
            
            # Generate query embedding with Gemini
            gemini_client = get_gemini_client()
            query_embedding = gemini_client.generate_query_embedding(question)
            logger.info(f"[LISA RAG] Generated query embedding with Gemini, dimension: {len(query_embedding)}")

            # Vector search in Azure AI Search
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=30,
                fields="contentVector",
            )

            search_results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_query,
                select=["file_name", "blob_name", "chunk_id", "chunk_index", "content"],
                top=30,
            )

            search_results_list = list(search_results)
            logger.info(f"[LISA RAG] Vector search returned {len(search_results_list)} documents")

            if not search_results_list:
                logger.warning(f"[LISA RAG] No documents found in search")
                return "Sorry, I couldn't find any relevant information in the documents.", [], []

            # Extract content from top results
            retrieved_contents = []
            for result in search_results_list[:5]:
                content = result.get("content", "")
                if content:
                    retrieved_contents.append(content)

            if not retrieved_contents:
                logger.warning(f"[LISA RAG] No content in search results")
                return "Sorry, I couldn't find any relevant information in the documents.", [], []

            document_context = "\n\n".join(retrieved_contents[:5])

            logger.info(f"[LISA RAG] Step 4: ✅ Prompt construction completed")

            # ============================================================
            # STEP 5: ANSWER GENERATION (CROSS-ATTENTION LEVEL 2)
            # ============================================================
            logger.info(f"[LISA RAG] =========================================")
            logger.info(f"[LISA RAG] STEP 5: ANSWER GENERATION (CROSS-ATTENTION LEVEL 2)")
            logger.info(f"[LISA RAG] Goal: Generate answer grounded in retrieved documents")
            logger.info(f"[LISA RAG] Method: Gemini with cross-attention to context")
            logger.info(f"[LISA RAG] Step 5: Starting LLM generation with Gemini...")

            # Build prompt with context
            prompt = f"""You are Lisa, an AI assistant specialized in Gap Analysis Compliance.

Document Context:
{document_context}

Question: {question}

Instructions:
- Answer based ONLY on the provided document context
- Use exact quotes and data from the documents
- If information is not in the context, say "Not specified in the documents"
- Be precise and cite specific information

Please provide a clear, concise answer based on the document context.
"""

            logger.info(f"DEBUG: Lisa RAG - Calling Gemini for generation")

            # Call Gemini for answer generation
            try:
                answer = gemini_client.generate_content(
                    prompt=prompt,
                    temperature=0.1,
                    max_output_tokens=2000,
                )

                logger.info(f"[LISA RAG] Step 5: LLM response received from Gemini")

            except Exception as e:
                logger.error(f"Error calling Gemini: {e}", exc_info=True)
                return f"Sorry, I encountered an error: {str(e)}", [], []
            
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

            logger.info(f"DEBUG: Lisa RAG - Created {len(references)} references from search results")
            logger.info(f"DEBUG: Lisa RAG - Retrieved {len(retrieved_chunks)} chunks with scores")

            logger.info(f"[LISA RAG] Step 5: ✅ Cross-Attention Level 2 completed")
            logger.info(f"[LISA RAG] Step 5: Answer length: {len(answer)} characters")
            logger.info(f"[LISA RAG] Step 5: References extracted: {len(references)}")
            logger.info(f"[LISA RAG] =========================================")
            logger.info(f"[LISA RAG] ✅ RAG FLOW COMPLETED with Gemini")

            return answer, references, retrieved_chunks
            
        except Exception as e:
            logger.error(f"Error in Lisa RAG chat: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}", [], []
    
    def _get_references_from_citations(
        self,
        citations: List,
        question: str,
        company_id: int,
        filter_query: Optional[str] = None
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Get references from top documents (same as Azure OpenAI queried).
        Simplified approach: query Azure AI Search with same parameters and get unique files.
        
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
            logger.warning("DEBUG: Lisa RAG - No citations provided, returning empty references")
            return [], []
        
        try:
            logger.debug(f"DEBUG: Lisa RAG - Getting references, citations count: {len(citations)}")
            
            # Create embedding for question (same as Azure OpenAI used)
            client = get_lisa_rag_client()
            embedding_response = client.embeddings.create(
                model=EMBEDDING_DEPLOYMENT_ID,
                input=[question],
                dimensions=EMBEDDING_DIMENSIONS,  # Specify 256 dimensions - CRITICAL!
            )
            query_embedding = embedding_response.data[0].embedding
            logger.debug(f"DEBUG: Lisa RAG - Created query embedding, dimension: {len(query_embedding)}")
            
            # STEP 1: Fast Retrieval (NO CROSS-ATTENTION)
            # Retrieve many candidate chunks quickly (top 20-50)
            # This is fast but not deeply accurate - uses cosine similarity only
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=30,  # Retrieve 30-50 candidates for reranking (as per RAG flow)
                fields="contentVector",
            )
            
            logger.info(f"[LISA RAG] Step 1: Fast Retrieval - Vector search with filter: {filter_query}")
            
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
            logger.info(f"[LISA RAG] Step 1: Fast Retrieval - Vector search returned {len(search_results_list)} documents")
            
            if not search_results_list:
                logger.warning(f"[LISA RAG] No documents found in Azure AI Search for question: {question[:50]}... with filter: {filter_query}")
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
            
            # ============================================================
            # STEP 3: RE-RANKING (CROSS-ATTENTION LEVEL 1)
            # ============================================================
            logger.info(f"[LISA RAG] =========================================")
            logger.info(f"[LISA RAG] STEP 3: RE-RANKING (CROSS-ATTENTION LEVEL 1)")
            logger.info(f"[LISA RAG] Goal: Let the query read each chunk and score relevance")
            logger.info(f"[LISA RAG] Method: Cross-Encoder (sentence-transformers)")
            logger.info(f"[LISA RAG] Input: {len(chunks_for_reranking)} chunks to rerank")
            logger.info(f"[LISA RAG] Output: Top 5 chunks (range: 3-5)")
            
            try:
                from companies.sdk.rag_reranker import rerank_chunks
                
                logger.info(f"[LISA RAG] Step 3: Starting Cross-Encoder reranking...")
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
                    logger.info(f"[LISA RAG] Step 3: ✅ Cross-Attention Level 1 completed")
                    logger.info(f"[LISA RAG] Step 3: Top 1 score: {top1_score:.4f}, Top 3 score: {top3_score:.4f}, Top 5 score: {top5_score:.4f}")
                    logger.info(f"[LISA RAG] Step 3: Selected {len(top_chunks)} chunks for prompt construction")
                else:
                    logger.info(f"[LISA RAG] Step 3: ✅ Reranking completed - no chunks returned")
                
                # Use reranked chunks (top 3-5) for references
                ranked_results = top_chunks if top_chunks else chunks_for_reranking[:5]
            except Exception as rerank_exc:
                logger.warning(f"[LISA RAG] Step 3: ⚠️ Reranking failed: {rerank_exc}, using original vector search results")
                logger.exception(rerank_exc)
                # Fallback: use original vector search results (top 5)
                ranked_results = chunks_for_reranking[:5]
            
            # ============================================================
            # STEP 4: PROMPT CONSTRUCTION
            # ============================================================
            logger.info(f"[LISA RAG] =========================================")
            logger.info(f"[LISA RAG] STEP 4: PROMPT CONSTRUCTION")
            logger.info(f"[LISA RAG] Goal: Force the LLM to answer using only provided context")
            logger.info(f"[LISA RAG] Method: System prompt + User question + Retrieved context")
            
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
                
                logger.debug(f"DEBUG: Lisa RAG - Result: file_name={file_name}, blob_name={blob_name}, chunk_id={chunk_id}, score={score}")
                
                # Add to retrieved_chunks
                if chunk_id:
                    retrieved_chunks.append({
                        "id": chunk_id,
                        "score": float(score) if score else 0.0
                    })
                elif blob_name and chunk_index is not None:
                    # Fallback: create chunk_id from blob_name and chunk_index
                    import hashlib
                    blob_hash = hashlib.md5(blob_name.encode()).hexdigest()[:8]
                    chunk_id = f"{blob_hash}_{chunk_index}"
                    retrieved_chunks.append({
                        "id": chunk_id,
                        "score": float(score) if score else 0.0
                    })
                
                # Extract unique file references
                if file_name and blob_name:
                    file_key = (file_name, blob_name)
                    if file_key not in seen_files:
                        seen_files.add(file_key)
                        references.append({
                            "blob_name": blob_name,
                            "file_name": file_name,
                        })
                        logger.debug(f"DEBUG: Lisa RAG - Added reference: {file_name}")
            
            logger.info(f"DEBUG: Lisa RAG - Extracted {len(references)} unique file references and {len(retrieved_chunks)} chunks")
            return references, retrieved_chunks
            
        except Exception as e:
            logger.error(f"Error getting references from citations: {e}", exc_info=True)
            return [], []

