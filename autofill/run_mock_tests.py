import sys
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import os

# -------------------------------------------------------------------------
# 1. SETUP MOCKS BEFORE IMPORTING MODULES
# -------------------------------------------------------------------------
# Mock Django settings
mock_settings = MagicMock()
mock_settings.SDK_DEBUG = True
mock_settings.AUTOFILL_AI_AZURE_AI_SEARCH_ENDPOINT = "https://mock-search.search.windows.net"
mock_settings.AUTOFILL_AI_AZURE_AI_SEARCH_KEY = "mock-search-key"
mock_settings.AUTOFILL_AI_AZURE_AI_SEARCH_INDEX_NAME = "mock-index"
mock_settings.AUTOFILL_AI_AZURE_AI_SEARCH_INDEXER = "mock-indexer"
mock_settings.AUTOFILL_AI_AZURE_STORAGE_BLOB_URL = "https://mock.blob.core.windows.net"
mock_settings.AUTOFILL_AI_AZURE_STORAGE_CONTAINER_KEY = "mock-storage-key"
mock_settings.AUTOFILL_AI_AZURE_STORAGE_CONTAINER_NAME = "mock-container"
mock_settings.RAG_DOCUMENT_INTELLIGENCE_ENDPOINT = "https://mock-doc-intel.cognitiveservices.azure.com/"
mock_settings.RAG_DOCUMENT_INTELLIGENCE_KEY = "mock-doc-intel-key"
mock_settings.RAG_DOCUMENT_INTELLIGENCE_MODEL = "prebuilt-layout"

# Mock django module
mock_django_conf = MagicMock()
mock_django_conf.settings = mock_settings
sys.modules["django.conf"] = mock_django_conf
sys.modules["django"] = MagicMock()

# Mock google.generativeai before import
sys.modules["google"] = MagicMock()
sys.modules["google.generativeai"] = MagicMock()

# -------------------------------------------------------------------------
# 2. IMPORT MODULES (Now safe to import)
# -------------------------------------------------------------------------
try:
    from autofill_ai import AiAutofill
    from lisa_rag import LisaRagDocumentProcessor, LisaRagChat
    from form_analyzer import FormAnalyzer, FieldType, FormField
except ImportError as e:
    print(f"Import warning: {e}. Attempting to mock missing libraries...")
    sys.modules["azure.core.credentials"] = MagicMock()
    sys.modules["azure.search.documents"] = MagicMock()
    sys.modules["azure.search.documents.indexes"] = MagicMock()
    sys.modules["azure.search.documents.models"] = MagicMock()
    sys.modules["azure.storage.blob"] = MagicMock()
    sys.modules["azure.ai.documentintelligence"] = MagicMock()

    # Retry import
    from autofill_ai import AiAutofill
    from lisa_rag import LisaRagDocumentProcessor, LisaRagChat
    from form_analyzer import FormAnalyzer, FieldType, FormField

# -------------------------------------------------------------------------
# 3. TEST LOGIC
# -------------------------------------------------------------------------

def test_form_analyzer():
    """Test FormAnalyzer functionality"""
    print("\n[TEST] Testing FormAnalyzer...")

    # Test field type detection
    field_type = FormAnalyzer.detect_field_type("Entity Contact Email")
    assert field_type == FieldType.EMAIL, f"Expected EMAIL, got {field_type}"
    print(f"   ✓ Email field detected correctly")

    field_type = FormAnalyzer.detect_field_type("Contact Phone")
    assert field_type == FieldType.PHONE, f"Expected PHONE, got {field_type}"
    print(f"   ✓ Phone field detected correctly")

    # Test option extraction
    options = FormAnalyzer.extract_options("Yes\nNo\nPlanned")
    assert options == ["Yes", "No", "Planned"], f"Expected ['Yes', 'No', 'Planned'], got {options}"
    print(f"   ✓ Options extracted correctly")

    # Test structured prompt building
    field = FormField("Test Field", FieldType.SELECT, options=["Option 1", "Option 2"])
    prompt = FormAnalyzer.build_structured_prompt(
        field=field,
        document_context="Sample document content",
    )
    assert "Option 1" in prompt
    assert "Option 2" in prompt
    assert "SELECT" in prompt or "select" in prompt.lower()
    print(f"   ✓ Structured prompt built correctly")

    # Test response parsing
    parsed = FormAnalyzer.parse_response('["Item 1", "Item 2"]', FieldType.CHECKBOX)
    assert parsed == ["Item 1", "Item 2"], f"Expected ['Item 1', 'Item 2'], got {parsed}"
    print(f"   ✓ Checkbox response parsed correctly")

    print("   [PASS] FormAnalyzer tests completed successfully")


async def test_autofill_generate_many():
    """Test AiAutofill.generate_many with structured form support"""
    print("\n[TEST] Testing AiAutofill.generate_many with structured forms...")

    class MockDatapoint:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.original_text = "original context"

    datapoints = [
        MockDatapoint(1, "Entity Name"),
        MockDatapoint(2, "Public authority/body?")
    ]

    autofill = AiAutofill()

    # Mock the AutofillRagChat
    with patch("autofill_ai.AutofillRagChat") as MockRagChatClass:
        mock_chat_instance = MockRagChatClass.return_value

        # Mock chat to return different responses
        def mock_chat_side_effect(*args, **kwargs):
            question = kwargs.get('question', '')
            if 'Entity Name' in question:
                return ("Acme Corporation", [], [])
            elif 'Public authority' in question:
                return ("No", [], [])
            return ("Mocked Answer", [], [])

        mock_chat_instance.chat.side_effect = mock_chat_side_effect

        # Run
        results = await autofill.generate_many(datapoints, company_id=123)

        # Verify
        print(f"   Results: {results}")
        assert "Entity Name" in results
        assert results["Entity Name"] == "Acme Corporation"
        assert "Public authority/body?" in results
        assert results["Public authority/body?"] == "No"
        print("   [PASS] generate_many with structured forms processed correctly")


def test_lisa_rag_indexing():
    """Test LisaRagDocumentProcessor with Gemini embeddings"""
    print("\n[TEST] Testing LisaRagDocumentProcessor with Gemini...")

    processor = LisaRagDocumentProcessor()

    # Mock internal components
    processor.doc_intelligence = MagicMock()
    processor.chunker = MagicMock()
    processor.indexer = MagicMock()
    processor.storage = MagicMock()

    # Setup return values
    processor.doc_intelligence.analyze_document.return_value = {"content": "Mock PDF content"}
    processor.doc_intelligence.format_structured_content.return_value = "Formatted Mock Content"
    processor.chunker.chunk_text.return_value = ["Chunk 1", "Chunk 2"]
    processor.indexer.index_document_chunks.return_value = 2  # 2 chunks indexed

    # Run
    count = processor.process_and_index_document_with_blob(
        file_path="/tmp/fake.pdf",
        file_name="fake.pdf",
        company_id=999,
        blob_name="fake_blob_path"
    )

    print(f"   Indexed Count: {count}")

    # Assertions
    processor.doc_intelligence.analyze_document.assert_called_once()
    processor.chunker.chunk_text.assert_called_with("Formatted Mock Content")
    processor.indexer.index_document_chunks.assert_called_once()

    assert count == 2
    print("   [PASS] Document processor with Gemini embeddings works correctly")


def test_gemini_client_mock():
    """Test that Gemini client can be mocked"""
    print("\n[TEST] Testing Gemini client initialization...")

    with patch("gemini_client.genai") as mock_genai:
        from gemini_client import GeminiClient

        # Create client
        client = GeminiClient(api_keys=["test_key_1", "test_key_2"])

        # Verify initialization
        assert len(client.api_keys) == 2
        assert client.current_key_index == 0
        print(f"   ✓ Client initialized with {len(client.api_keys)} keys")

        # Test key rotation
        client.rotate_key()
        assert client.current_key_index == 1
        print(f"   ✓ Key rotation works correctly")

        client.rotate_key()
        assert client.current_key_index == 0  # Should wrap around
        print(f"   ✓ Key rotation wraps around correctly")

        print("   [PASS] Gemini client initialization and rotation works correctly")


async def main():
    try:
        print("\n" + "="*60)
        print("Running Mock Tests for Gemini-Powered Autofill System")
        print("="*60)

        test_form_analyzer()
        test_gemini_client_mock()
        await test_autofill_generate_many()
        test_lisa_rag_indexing()

        print("\n" + "="*60)
        print("✅ All mock tests completed successfully!")
        print("="*60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
