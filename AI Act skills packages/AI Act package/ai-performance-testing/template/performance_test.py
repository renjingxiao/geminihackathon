from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval.dataset import EvaluationDataset
from deepeval.models import GeminiModel
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from deepeval.metrics import HallucinationMetric, FaithfulnessMetric
from deepeval.models import DeepEvalBaseLLM
import google.generativeai as genai
from tqdm import tqdm
import os
import concurrent.futures

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = GeminiModel(
    model="gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    temperature=0,
)

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

file_path = "./synthetic_data/20260125_141448.json"
loaded_dataset = EvaluationDataset()

loaded_dataset.add_goldens_from_json_file(
    file_path=file_path,
    input_key_name="input",
    expected_output_key_name="expected_output"
)

tested_model = CustomGeminiModel(
    model_name="models/gemini-pro-latest",
    api_key=GEMINI_API_KEY,
    temperature=0
)

def create_test_case(golden):
    actual_output = tested_model.generate(golden.input)
    return LLMTestCase(
        input=golden.input,
        actual_output=actual_output,
        context=golden.context,
        expected_output=golden.expected_output,
        retrieval_context=golden.context
    )

test_cases = []
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [executor.submit(create_test_case, golden) for golden in loaded_dataset.goldens]
    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        test_cases.append(future.result())

print(f"Loaded {len(test_cases)} synthetic test cases.")
faithfulness_metric = FaithfulnessMetric(
    threshold=0.95,
    model=model,
    include_reason=True
)

factual_accuracy_metric = GEval(
    name="Factual Accuracy & Citations",
    criteria="Determine if the answer is factually correct based on the context. Penalize any claim made without a supporting citation from the context.",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
    threshold=0.95,
    model=model,
)
completeness_metric = GEval(
    name="Completeness",
    criteria="Evaluate if the actual output provides a comprehensive answer to the input. It should not omit any key details provided in the retrieval context that are relevant to the question.",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
    threshold=0.90,
    model=model,
)
consistency_metric = HallucinationMetric(
    threshold=0.1,
    model=model,
)

evaluate(
    test_cases=test_cases,
    metrics=[faithfulness_metric, completeness_metric, consistency_metric]
)
