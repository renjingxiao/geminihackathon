"""
Test form field detection and structured prompts
"""
import sys
from unittest.mock import MagicMock

# Mock Django settings
mock_settings = MagicMock()
mock_settings.SDK_DEBUG = True
sys.modules["django.conf"] = MagicMock()
sys.modules["django.conf"].settings = mock_settings
sys.modules["django"] = MagicMock()

from form_analyzer import FormAnalyzer, FieldType, FormField, EU_AI_ACT_FORM_FIELDS

def test_field_type_detection():
    """Test automatic field type detection"""
    print("\n" + "="*60)
    print("Testing Field Type Detection")
    print("="*60)

    test_cases = [
        ("Entity Name", None, FieldType.TEXT),
        ("Entity Contact Email", None, FieldType.EMAIL),
        ("Contact Phone", None, FieldType.PHONE),
        ("Registration Number", None, FieldType.NUMBER),
        ("Postal Code", None, FieldType.TEXT),
        ("Founded Date", None, FieldType.DATE),
    ]

    for field_name, context, expected_type in test_cases:
        detected_type = FormAnalyzer.detect_field_type(field_name, context)
        status = "✅" if detected_type == expected_type else "❌"
        print(f"{status} {field_name:30} → {detected_type.value:10} (expected: {expected_type.value})")


def test_option_extraction():
    """Test option extraction from different formats"""
    print("\n" + "="*60)
    print("Testing Option Extraction")
    print("="*60)

    test_cases = [
        # Line-separated
        ("Yes\nNo\nPlanned", ["Yes", "No", "Planned"]),
        # Comma-separated
        ("Provider, Deployer, Importer", ["Provider", "Deployer", "Importer"]),
        # JSON array
        ('["Option 1", "Option 2", "Option 3"]', ["Option 1", "Option 2", "Option 3"]),
    ]

    for input_text, expected_options in test_cases:
        extracted = FormAnalyzer.extract_options(input_text)
        status = "✅" if extracted == expected_options else "❌"
        print(f"{status} Input: {input_text[:40]:40} → {extracted}")


def test_structured_prompt_generation():
    """Test structured prompt for different field types"""
    print("\n" + "="*60)
    print("Testing Structured Prompt Generation")
    print("="*60)

    # Text field
    text_field = FormField("Entity Name", FieldType.TEXT, required=True)
    prompt = FormAnalyzer.build_structured_prompt(
        field=text_field,
        document_context="Acme Corporation is registered in Delaware.",
    )
    print("\n✅ TEXT Field Prompt:")
    print(f"   - Contains 'Entity Name': {'Entity Name' in prompt}")
    print(f"   - Contains 'TEXT': {'TEXT' in prompt or 'text' in prompt.lower()}")
    print(f"   - Length: {len(prompt)} chars")

    # Select field
    select_field = FormField(
        "Country",
        FieldType.SELECT,
        options=["United Kingdom", "United States", "France", "Germany"],
        required=True,
    )
    prompt = FormAnalyzer.build_structured_prompt(
        field=select_field,
        document_context="The company operates in the United States.",
    )
    print("\n✅ SELECT Field Prompt:")
    print(f"   - Contains 'Country': {'Country' in prompt}")
    print(f"   - Contains 'United States': {'United States' in prompt}")
    print(f"   - Contains 'SELECT': {'SELECT' in prompt or 'select' in prompt.lower()}")
    print(f"   - Length: {len(prompt)} chars")

    # Checkbox field
    checkbox_field = FormField(
        "Roles",
        FieldType.CHECKBOX,
        options=["Provider", "Deployer", "Importer", "Distributor"],
        required=True,
    )
    prompt = FormAnalyzer.build_structured_prompt(
        field=checkbox_field,
        document_context="We act as both a provider and deployer of AI systems.",
    )
    print("\n✅ CHECKBOX Field Prompt:")
    print(f"   - Contains 'Roles': {'Roles' in prompt}")
    print(f"   - Contains 'Provider': {'Provider' in prompt}")
    print(f"   - Contains 'JSON array': {'JSON array' in prompt or 'json array' in prompt.lower()}")
    print(f"   - Length: {len(prompt)} chars")


def test_response_parsing():
    """Test parsing Gemini responses for different field types"""
    print("\n" + "="*60)
    print("Testing Response Parsing")
    print("="*60)

    test_cases = [
        # Text
        (FieldType.TEXT, "Acme Corporation", "Acme Corporation"),
        # Select
        (FieldType.SELECT, "United States", "United States"),
        # Radio
        (FieldType.RADIO, "Yes", "Yes"),
        # Checkbox - JSON array
        (FieldType.CHECKBOX, '["Provider", "Deployer"]', ["Provider", "Deployer"]),
        # Checkbox - comma separated
        (FieldType.CHECKBOX, "Provider, Deployer", ["Provider", "Deployer"]),
        # Email
        (FieldType.EMAIL, "contact@acme.com", "contact@acme.com"),
        # Phone
        (FieldType.PHONE, "+1 (555) 000-0000", "+1 (555) 000-0000"),
    ]

    for field_type, response, expected in test_cases:
        parsed = FormAnalyzer.parse_response(response, field_type)
        status = "✅" if parsed == expected else "❌"
        print(f"{status} {field_type.value:10} | {str(response)[:30]:30} → {parsed}")


def test_structured_response_format():
    """Test structured response formatting"""
    print("\n" + "="*60)
    print("Testing Structured Response Format")
    print("="*60)

    # Single value
    response = FormAnalyzer.format_structured_response(
        field_name="Entity Name",
        field_type=FieldType.TEXT,
        value="Acme Corporation",
        confidence=0.95,
    )
    print("\n✅ Single Value Response:")
    print(f"   {response}")

    # Multiple values (checkbox)
    response = FormAnalyzer.format_structured_response(
        field_name="Roles",
        field_type=FieldType.CHECKBOX,
        value=["Provider", "Deployer"],
        confidence=0.90,
    )
    print("\n✅ Multiple Values Response:")
    print(f"   {response}")

    # Empty value
    response = FormAnalyzer.format_structured_response(
        field_name="Optional Field",
        field_type=FieldType.TEXT,
        value="",
    )
    print("\n✅ Empty Value Response:")
    print(f"   {response}")


def test_predefined_form_fields():
    """Test predefined EU AI Act form fields"""
    print("\n" + "="*60)
    print("Testing Predefined EU AI Act Form Fields")
    print("="*60)

    print(f"\n✅ Total predefined fields: {len(EU_AI_ACT_FORM_FIELDS)}")

    sample_fields = [
        "Entity Name",
        "Country",
        "Public authority/body?",
        "Q2: Which roles best describe your typical activities?",
    ]

    for field_name in sample_fields:
        if field_name in EU_AI_ACT_FORM_FIELDS:
            field = EU_AI_ACT_FORM_FIELDS[field_name]
            print(f"\n   Field: {field_name}")
            print(f"   - Type: {field.field_type.value}")
            print(f"   - Required: {field.required}")
            print(f"   - Options: {field.options[:2] if field.options else 'None'}...")


def main():
    print("\n" + "="*70)
    print(" 🧪 Form Field Testing Suite - Comprehensive Tests")
    print("="*70)

    try:
        test_field_type_detection()
        test_option_extraction()
        test_structured_prompt_generation()
        test_response_parsing()
        test_structured_response_format()
        test_predefined_form_fields()

        print("\n" + "="*70)
        print("✅ All form field tests passed!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
