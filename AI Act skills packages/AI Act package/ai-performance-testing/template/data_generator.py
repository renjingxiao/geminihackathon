from deepeval.synthesizer import Synthesizer
from deepeval.models import GeminiModel
from deepeval.synthesizer.config import ContextConstructionConfig
from deepeval.models.base_model import DeepEvalBaseEmbeddingModel
from deepeval.models import DeepEvalBaseLLM
import google.generativeai as genai
import os
import logging

os.environ["DEEPEVAL_LOG_STACK_TRACES"] = "True"

logging.basicConfig(level=logging.INFO)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class CustomGeminiModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str, api_key: str, temperature: float = 0):
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(model_name=self.model_name)

    def load_model(self):
        return self._model

    def generate(self, prompt: str) -> str:
        if not prompt:
            return "This is an empty query."
        response = self._model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.temperature
            )
        )
        return response.text

    async def a_generate(self, prompt: str) -> str:
        # Gemini client library does not have a native async generate yet,
        # so we'll run the sync version in an executor.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate,
            prompt
        )

    def get_model_name(self):
        return self.model_name

model = CustomGeminiModel(
    model_name="gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    temperature=0,
)
class GeminiEmbeddingModel(DeepEvalBaseEmbeddingModel):
    def __init__(self, model: str = "models/embedding-001"):
        genai.configure(api_key=GEMINI_API_KEY)
        self._model = model
        super().__init__(model)

    def load_model(self):
        # The Gemini API doesn't require a model to be explicitly loaded.
        # This method can be a no-op.
        return self._model

    def embed_text(self, text: str):
        result = genai.embed_content(model=self.model, content=text)
        return result["embedding"]

    def embed_texts(self, texts: list[str]):
        result = genai.embed_content(model=self.model, content=texts)
        return result["embedding"]

    async def a_embed_text(self, text: str):
        # For simplicity, we'll use the synchronous version in a thread.
        # A true async implementation would require an async-compatible library.
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_text, text)

    async def a_embed_texts(self, texts: list[str]):
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_texts, texts)

    def get_model_name(self):
        return f"Gemini {self.model}"

# Initialize the synthesizer
synthesizer = Synthesizer(model=model, async_mode=False)

gemini_embedder = GeminiEmbeddingModel()
context_config = ContextConstructionConfig(
    # chunk_size=50,  # Reduced chunk size
    # min_context_length=10,  # Reduced min context length
    embedder=gemini_embedder,
    critic_model=model,
)

def files_under_directory(directory):
    import os
    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_paths.append(os.path.join(root, file))
    return file_paths

# Generate 'goldens' from your documents (PDFs, TXT, etc.)
goldens = synthesizer.generate_goldens_from_docs(
    document_paths=files_under_directory('/Users/huzhanbo/dev/geminihackathon/AI Act skills packages/AI Act package/ai-testing/resource'),
    include_expected_output=True,
    context_construction_config=context_config
)

# Optional: Save them for later so you don't burn tokens regenerating
synthesizer.save_as(file_type='json', directory="./synthetic_data")