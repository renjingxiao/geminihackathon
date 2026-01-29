"""
Gemini Client with API Key Rotation
Supports multiple API keys with automatic failover
"""
import logging
import time
from typing import List, Optional, Dict, Any
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Gemini API Keys from TASK.md
GEMINI_API_KEYS = [
    "AIzaSyAbi-ahThqgf0rzMRlv2dhn1yyA8EMuGfU",  # Key 1
    "AIzaSyDvmvMqCkMQjm0QXsAr-U581pce0cOi3I0",  # Key 2
    "AIzaSyCTWJnEwGsG-tWvM1-xzV3s8YMXtjlvY_A",  # Key 3 (including gemini 3)
    "AIzaSyDh-DqGGf8VEXAbbBZBL68lyJ9wllZAjrw",  # Key 4
    "AIzaSyDvq0H4clMtq2XqactVjInMwCbE3ih5bio",  # Key 5
]

# Models
GEMINI_CHAT_MODEL = "gemini-1.5-pro"  # For chat/completion
GEMINI_EMBEDDING_MODEL = "models/embedding-001"  # For embeddings (768 dimensions)
EMBEDDING_DIMENSIONS = 768  # Gemini embedding-001 uses 768 dimensions


class GeminiClient:
    """
    Gemini client with automatic API key rotation on failure.
    """

    def __init__(self, api_keys: Optional[List[str]] = None):
        """
        Initialize Gemini client with multiple API keys.

        Args:
            api_keys: List of Gemini API keys (default: GEMINI_API_KEYS)
        """
        self.api_keys = api_keys or GEMINI_API_KEYS
        self.current_key_index = 0
        self.configure_current_key()

        logger.info(f"Initialized GeminiClient with {len(self.api_keys)} API keys")

    def configure_current_key(self):
        """Configure genai with current API key"""
        current_key = self.api_keys[self.current_key_index]
        genai.configure(api_key=current_key)
        logger.debug(f"Configured Gemini with key index {self.current_key_index}")

    def rotate_key(self):
        """Rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.configure_current_key()
        logger.warning(f"Rotated to API key index {self.current_key_index}")

    def generate_content(
        self,
        prompt: str,
        model: str = GEMINI_CHAT_MODEL,
        max_retries: int = 3,
        temperature: float = 0.1,
        max_output_tokens: int = 8192,
    ) -> str:
        """
        Generate content using Gemini with automatic key rotation on failure.

        Args:
            prompt: Input prompt
            model: Model name (default: gemini-1.5-pro)
            max_retries: Maximum retry attempts across all keys
            temperature: Temperature for generation
            max_output_tokens: Maximum output tokens

        Returns:
            Generated text

        Raises:
            Exception: If all keys fail
        """
        attempts = 0
        last_exception = None

        while attempts < max_retries:
            try:
                model_instance = genai.GenerativeModel(model)

                generation_config = genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )

                logger.debug(f"Generating content with key index {self.current_key_index}, attempt {attempts + 1}")
                response = model_instance.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                # Extract text from response
                if hasattr(response, 'text'):
                    return response.text
                elif hasattr(response, 'parts'):
                    return ''.join(part.text for part in response.parts if hasattr(part, 'text'))
                else:
                    logger.warning(f"Unexpected response format: {response}")
                    return ""

            except Exception as e:
                last_exception = e
                logger.error(f"Error with key index {self.current_key_index}: {e}")

                attempts += 1
                if attempts < max_retries:
                    self.rotate_key()
                    time.sleep(1)  # Brief pause before retry
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    raise Exception(f"Gemini generation failed after {max_retries} attempts: {last_exception}")

        raise Exception(f"Failed to generate content: {last_exception}")

    def generate_embeddings(
        self,
        texts: List[str],
        model: str = GEMINI_EMBEDDING_MODEL,
        max_retries: int = 3,
    ) -> List[List[float]]:
        """
        Generate embeddings using Gemini with automatic key rotation on failure.

        Args:
            texts: List of texts to embed
            model: Embedding model name (default: models/embedding-001)
            max_retries: Maximum retry attempts across all keys

        Returns:
            List of embedding vectors (each 768 dimensions)

        Raises:
            Exception: If all keys fail
        """
        attempts = 0
        last_exception = None

        while attempts < max_retries:
            try:
                logger.debug(f"Generating embeddings for {len(texts)} texts with key index {self.current_key_index}")

                embeddings = []
                for text in texts:
                    result = genai.embed_content(
                        model=model,
                        content=text,
                        task_type="retrieval_document",  # For indexing documents
                    )
                    embeddings.append(result['embedding'])

                # Validate dimensions
                if embeddings and len(embeddings[0]) != EMBEDDING_DIMENSIONS:
                    logger.error(f"Unexpected embedding dimension: {len(embeddings[0])}, expected {EMBEDDING_DIMENSIONS}")
                    raise ValueError(f"Embedding dimension mismatch: got {len(embeddings[0])}, expected {EMBEDDING_DIMENSIONS}")

                logger.debug(f"Successfully generated {len(embeddings)} embeddings, dimension: {EMBEDDING_DIMENSIONS}")
                return embeddings

            except Exception as e:
                last_exception = e
                logger.error(f"Error generating embeddings with key index {self.current_key_index}: {e}")

                attempts += 1
                if attempts < max_retries:
                    self.rotate_key()
                    time.sleep(1)
                else:
                    logger.error(f"All {max_retries} attempts failed for embeddings")
                    raise Exception(f"Gemini embedding generation failed after {max_retries} attempts: {last_exception}")

        raise Exception(f"Failed to generate embeddings: {last_exception}")

    def generate_query_embedding(
        self,
        query: str,
        model: str = GEMINI_EMBEDDING_MODEL,
        max_retries: int = 3,
    ) -> List[float]:
        """
        Generate embedding for a query (used for search).

        Args:
            query: Query text
            model: Embedding model name
            max_retries: Maximum retry attempts

        Returns:
            Embedding vector (768 dimensions)
        """
        attempts = 0
        last_exception = None

        while attempts < max_retries:
            try:
                logger.debug(f"Generating query embedding with key index {self.current_key_index}")

                result = genai.embed_content(
                    model=model,
                    content=query,
                    task_type="retrieval_query",  # For search queries
                )

                embedding = result['embedding']

                # Validate dimensions
                if len(embedding) != EMBEDDING_DIMENSIONS:
                    logger.error(f"Unexpected embedding dimension: {len(embedding)}, expected {EMBEDDING_DIMENSIONS}")
                    raise ValueError(f"Embedding dimension mismatch: got {len(embedding)}, expected {EMBEDDING_DIMENSIONS}")

                logger.debug(f"Successfully generated query embedding, dimension: {EMBEDDING_DIMENSIONS}")
                return embedding

            except Exception as e:
                last_exception = e
                logger.error(f"Error generating query embedding with key index {self.current_key_index}: {e}")

                attempts += 1
                if attempts < max_retries:
                    self.rotate_key()
                    time.sleep(1)
                else:
                    logger.error(f"All {max_retries} attempts failed for query embedding")
                    raise Exception(f"Gemini query embedding failed after {max_retries} attempts: {last_exception}")

        raise Exception(f"Failed to generate query embedding: {last_exception}")


# Global client instance
_gemini_client = None


def get_gemini_client() -> GeminiClient:
    """Get or create global Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
