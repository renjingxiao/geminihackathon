"""
Form Analyzer - Structured Form Field Processing
Supports text, select, radio, checkbox, and formatted input fields
"""
import json
import logging
import re
from typing import Dict, List, Optional, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


class FieldType(str, Enum):
    """Form field types"""
    TEXT = "text"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"


class FormField:
    """Represents a form field with metadata"""

    def __init__(
        self,
        name: str,
        field_type: FieldType,
        options: Optional[List[str]] = None,
        required: bool = False,
        description: Optional[str] = None,
    ):
        self.name = name
        self.field_type = field_type
        self.options = options or []
        self.required = required
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "options": self.options,
            "required": self.required,
            "description": self.description,
        }


class FormAnalyzer:
    """Analyzes and processes form fields with AI assistance"""

    @staticmethod
    def detect_field_type(field_name: str, field_context: Optional[str] = None) -> FieldType:
        """
        Detect field type from field name and context.

        Args:
            field_name: Name of the field
            field_context: Additional context (e.g., options, placeholder)

        Returns:
            Detected FieldType
        """
        field_name_lower = field_name.lower()

        # Email detection
        if any(keyword in field_name_lower for keyword in ["email", "e-mail"]):
            return FieldType.EMAIL

        # Phone detection
        if any(keyword in field_name_lower for keyword in ["phone", "telephone", "mobile"]):
            return FieldType.PHONE

        # Number detection
        if any(keyword in field_name_lower for keyword in ["number", "count", "quantity", "amount"]):
            return FieldType.NUMBER

        # Date detection
        if any(keyword in field_name_lower for keyword in ["date", "year", "month", "day"]):
            return FieldType.DATE

        # Checkbox detection (multi-select keywords)
        if field_context:
            context_lower = field_context.lower()
            if "select all that apply" in context_lower or "multiple" in context_lower:
                return FieldType.CHECKBOX

        # Radio/Select detection (single choice keywords)
        if field_context:
            context_lower = field_context.lower()
            if any(keyword in context_lower for keyword in ["yes/no", "select an option", "choose one"]):
                # If only 2-3 options, likely radio
                if field_context.count("\n") <= 3:
                    return FieldType.RADIO
                return FieldType.SELECT

        # Default to text
        return FieldType.TEXT

    @staticmethod
    def extract_options(field_context: str) -> List[str]:
        """
        Extract options from field context.

        Args:
            field_context: Field context containing options

        Returns:
            List of option strings
        """
        if not field_context:
            return []

        # Try to parse as JSON array
        try:
            options = json.loads(field_context)
            if isinstance(options, list):
                return [str(opt) for opt in options]
        except:
            pass

        # Try line-separated options
        lines = [line.strip() for line in field_context.split("\n") if line.strip()]
        if len(lines) > 1:
            return lines

        # Try comma-separated
        if "," in field_context:
            return [opt.strip() for opt in field_context.split(",") if opt.strip()]

        return []

    @staticmethod
    def build_structured_prompt(
        field: FormField,
        document_context: str,
        original_question: Optional[str] = None,
    ) -> str:
        """
        Build a structured prompt for Gemini based on field type.

        Args:
            field: FormField object
            document_context: Context from uploaded documents
            original_question: Original question/field description

        Returns:
            Structured prompt string
        """
        base_context = f"""You are a precise document analyzer for form autofill.

Field Name: {field.name}
Field Type: {field.field_type.value}
Required: {field.required}
"""

        if original_question:
            base_context += f"Question: {original_question}\n"

        if field.description:
            base_context += f"Description: {field.description}\n"

        base_context += f"\nDocument Context:\n{document_context}\n\n"

        # Type-specific instructions
        if field.field_type == FieldType.TEXT:
            instructions = """Extract and return ONLY the relevant text information from the document.
- Use exact quotes and data from the document
- If no relevant information is found, return: "Not specified in the documents"
- Do not generate or assume information
- Return plain text (or HTML with <ul>, <li>, <b> tags if structured)"""

        elif field.field_type == FieldType.SELECT:
            options_str = "\n".join([f"- {opt}" for opt in field.options])
            instructions = f"""Select the MOST appropriate option from the list below based on the document.

Available Options:
{options_str}

CRITICAL:
- Return ONLY the exact option text from the list above
- If multiple options seem relevant, choose the best match
- If no option matches, return: "Not specified in the documents"
- Do not create new options or modify existing ones"""

        elif field.field_type == FieldType.RADIO:
            options_str = "\n".join([f"- {opt}" for opt in field.options])
            instructions = f"""Select ONE option from the list below based on the document.

Available Options:
{options_str}

CRITICAL:
- Return ONLY the exact option text from the list above
- Choose the single best match
- If unclear, return: "Not specified in the documents"
- Do not create new options"""

        elif field.field_type == FieldType.CHECKBOX:
            options_str = "\n".join([f"- {opt}" for opt in field.options])
            instructions = f"""Select ALL applicable options from the list below based on the document.

Available Options:
{options_str}

CRITICAL:
- Return a JSON array of selected options, e.g., ["Option 1", "Option 3"]
- Include all options that apply according to the document
- Only select options that are explicitly mentioned or clearly implied
- If none apply, return: []
- Use exact option text from the list above"""

        elif field.field_type == FieldType.EMAIL:
            instructions = """Extract the email address from the document.
- Return ONLY the email in valid format (e.g., contact@company.com)
- If no email is found, return: "Not specified in the documents"
- Do not generate fake emails"""

        elif field.field_type == FieldType.PHONE:
            instructions = """Extract the phone number from the document.
- Return the phone number in a standard format (e.g., +1 (555) 000-0000)
- If no phone is found, return: "Not specified in the documents"
- Do not generate fake numbers"""

        elif field.field_type == FieldType.NUMBER:
            instructions = """Extract the relevant number from the document.
- Return ONLY the numeric value
- If no number is found, return: "Not specified in the documents"
- Do not generate or estimate numbers"""

        elif field.field_type == FieldType.DATE:
            instructions = """Extract the relevant date from the document.
- Return the date in ISO format (YYYY-MM-DD) if possible
- If no date is found, return: "Not specified in the documents"
- Do not generate or assume dates"""

        else:
            instructions = "Extract relevant information from the document."

        return base_context + instructions

    @staticmethod
    def parse_response(response: str, field_type: FieldType) -> Union[str, List[str]]:
        """
        Parse Gemini response based on field type.

        Args:
            response: Raw response from Gemini
            field_type: Type of the field

        Returns:
            Parsed response (string or list for checkboxes)
        """
        response = response.strip()

        # Handle empty or "not found" responses
        if not response or "not specified" in response.lower():
            return "" if field_type != FieldType.CHECKBOX else []

        # For checkbox, try to parse JSON array
        if field_type == FieldType.CHECKBOX:
            try:
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except:
                # Try to extract from text
                # Look for items in brackets or quoted
                matches = re.findall(r'"([^"]+)"', response)
                if matches:
                    return matches

                # Fallback: split by comma or newline
                if "," in response:
                    return [item.strip() for item in response.split(",") if item.strip()]
                elif "\n" in response:
                    return [item.strip("- •*") for item in response.split("\n") if item.strip()]

            return []

        # For other types, return as string (cleaned)
        return response.strip()

    @staticmethod
    def format_structured_response(
        field_name: str,
        field_type: FieldType,
        value: Union[str, List[str]],
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Format the final structured response.

        Args:
            field_name: Name of the field
            field_type: Type of the field
            value: Extracted value
            confidence: Optional confidence score

        Returns:
            Structured response dictionary
        """
        response = {
            "field_name": field_name,
            "field_type": field_type.value,
            "value": value,
            "has_value": bool(value) if not isinstance(value, list) else len(value) > 0,
        }

        if confidence is not None:
            response["confidence"] = confidence

        return response


# Common field definitions for EU AI Act compliance forms
EU_AI_ACT_FORM_FIELDS = {
    "Entity Name": FormField("Entity Name", FieldType.TEXT, required=True),
    "Registration Number": FormField("Registration Number", FieldType.TEXT, required=True),
    "Headquarter Address": FormField("Headquarter Address", FieldType.TEXT, required=True),
    "Country": FormField(
        "Country",
        FieldType.SELECT,
        options=["United Kingdom", "United States", "France", "Germany", "Other"],
        required=True,
    ),
    "Postal Code": FormField("Postal Code", FieldType.TEXT, required=True),
    "Legal Representative": FormField("Legal Representative", FieldType.TEXT, required=True),
    "Entity Contact Email": FormField("Entity Contact Email", FieldType.EMAIL, required=True),
    "Contact Phone": FormField("Contact Phone", FieldType.PHONE),
    "Public authority/body?": FormField(
        "Public authority/body?",
        FieldType.RADIO,
        options=["Yes", "No"],
        required=True,
    ),
    "Internal AI compliance owner?": FormField(
        "Internal AI compliance owner?",
        FieldType.RADIO,
        options=["Yes", "No", "Planned"],
        required=True,
    ),
    "Q1: Do you place AI systems and/or GPAI models on the EU/EEA market?": FormField(
        "Q1: Do you place AI systems and/or GPAI models on the EU/EEA market?",
        FieldType.RADIO,
        options=["Yes", "No"],
        required=True,
    ),
    "Q2: Which roles best describe your typical activities?": FormField(
        "Q2: Which roles best describe your typical activities?",
        FieldType.CHECKBOX,
        options=["Provider", "Deployer", "Importer", "Distributor"],
        required=True,
    ),
    "Q1: Users: Which internal teams or external contractors use AI systems?": FormField(
        "Q1: Users: Which internal teams or external contractors use AI systems?",
        FieldType.CHECKBOX,
        options=[
            "Product / Engineering",
            "Data / ML team",
            "Operations / Analysts",
            "HR / Recruitment",
            "Compliance / Legal",
            "Customer support",
            "Sales / Marketing",
            "Senior management",
            "External contractors / service providers",
        ],
        required=True,
    ),
}
