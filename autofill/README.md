# 🚀 Gemini-Powered Autofill System

AI-powered form autofill system using Google Gemini for intelligent document processing and structured form field support.

## ✨ Features

✅ **Gemini Integration**
- Google Gemini 1.5 Pro for intelligent text generation
- Gemini embedding-001 for semantic search (768-dim)
- 5 API keys with automatic rotation on failure

✅ **Structured Form Support**
- Text fields (free text input)
- Email, Phone, Number, Date (formatted inputs)
- Select/Radio (single choice from options)
- Checkbox (multiple selections)

✅ **RAG Pipeline**
- Azure Document Intelligence for document analysis
- Azure AI Search for vector storage
- Intelligent chunking and retrieval
- Company-specific document filtering

## 📦 Installation

```bash
# Install Gemini SDK
pip install google-generativeai

# Install Azure dependencies (if not already installed)
pip install azure-storage-blob azure-search-documents azure-ai-documentintelligence
```

## 🎯 Quick Start

### Basic Usage

```python
from autofill.autofill_ai import AiAutofill

autofill = AiAutofill()

# Text field
result = await autofill.generate_one(
    message="Entity Name",
    company_id=123
)
# → {"Entity Name": "Acme Corporation"}

# Radio button (with options)
result = await autofill.generate_one(
    message="Public authority/body?",
    company_id=123,
    field_type="radio",
    field_options=["Yes", "No"],
    return_structured=True
)
# → {"field_name": "Public authority/body?", "field_type": "radio", "value": "No"}

# Checkbox (multiple selections)
result = await autofill.generate_one(
    message="Select applicable roles",
    company_id=123,
    field_type="checkbox",
    field_options=["Provider", "Deployer", "Importer"],
    return_structured=True
)
# → {"field_name": "...", "field_type": "checkbox", "value": ["Provider", "Deployer"]}
```

### Bulk Processing

```python
datapoints = [
    DataPoint(id=1, name="Entity Name"),
    DataPoint(id=2, name="Registration Number"),
    DataPoint(id=3, name="Country"),
]

results = await autofill.generate_many(
    datapoints=datapoints,
    company_id=123,
    batch_size=10
)
```

## 🏗️ Architecture

```
Documents → Blob Storage → Doc Intelligence → Chunking
                                                  ↓
                                          Gemini Embedding
                                                  ↓
User Query → Gemini Embedding → Vector Search (Azure AI) → Gemini LLM → Response
```

## 📁 Files

- **`gemini_client.py`** - Gemini API client with key rotation
- **`form_analyzer.py`** - Form field type detection & structured prompts
- **`autofill_ai.py`** - Main autofill logic with Gemini RAG
- **`lisa_rag.py`** - Document processing and indexing
- **`run_mock_tests.py`** - Comprehensive test suite

## 🧪 Testing

```bash
cd /home/kali/Code/geminihackathon/autofill
python run_mock_tests.py
```

Expected: All tests pass ✅

## ⚙️ Configuration

### Gemini API Keys

Defined in `gemini_client.py` (5 keys with auto-rotation):

```python
GEMINI_API_KEYS = [
    "AIzaSyAbi-ahThqgf0rzMRlv2dhn1yyA8EMuGfU",  # Key 1
    "AIzaSyDvmvMqCkMQjm0QXsAr-U581pce0cOi3I0",  # Key 2
    "AIzaSyCTWJnEwGsG-tWvM1-xzV3s8YMXtjlvY_A",  # Key 3
    "AIzaSyDh-DqGGf8VEXAbbBZBL68lyJ9wllZAjrw",  # Key 4
    "AIzaSyDvq0H4clMtq2XqactVjInMwCbE3ih5bio",  # Key 5
]
```

### Azure AI Search Index

⚠️ **Important**: Update index to support 768-dimensional vectors:

```json
{
    "name": "contentVector",
    "type": "Collection(Edm.Single)",
    "dimensions": 768,  // Changed from 256 to 768
    "vectorSearchProfile": "vector-profile"
}
```

## 🎯 Supported Form Fields

| Type | Description | Example |
|------|-------------|---------|
| `text` | Free text | "Acme Corp" |
| `email` | Email address | "contact@acme.com" |
| `phone` | Phone number | "+1 (555) 000-0000" |
| `select` | Dropdown | "United Kingdom" |
| `radio` | Single choice | "Yes" |
| `checkbox` | Multiple choice | `["Provider", "Deployer"]` |

## 📊 Monitoring

Key logs to watch:

```log
🔵 [AUTOFILL] Using RAG with company_id: 123
🔵 [AUTOFILL RAG] Calling Gemini for generation
🟢 [AUTOFILL RAG] Valid answer found - length: 1234
⚠️  Rotated to API key index 1  # Key rotation occurred
```

## 🐛 Troubleshooting

### No documents found
- Check if documents are uploaded for the company
- Verify `company_id` filter

### Dimension mismatch error
- Update Azure AI Search index to 768 dimensions
- Re-index documents

### API rate limits
- System automatically rotates keys
- Monitor rotation frequency in logs

## 📚 Documentation

- **[Implementation Guide](IMPLEMENTATION_GUIDE.md)** - Detailed setup and usage
- **[Task Requirements](TASK.md)** - Original requirements

## ✅ Requirements Checklist

- [x] Migrate from Azure OpenAI to Google Gemini
- [x] Use 5 Gemini API keys with auto-rotation
- [x] Support text form fields
- [x] Support select/dropdown fields
- [x] Support radio buttons
- [x] Support checkboxes (multi-select)
- [x] Support formatted inputs (email, phone, etc.)
- [x] Maintain Azure AI Search vector database
- [x] Process only new uploaded documents
- [x] Comprehensive test suite

## 🎉 Summary

**What Changed:**
- ✅ Azure OpenAI → Google Gemini
- ✅ 256-dim → 768-dim embeddings
- ✅ Text-only → Structured form fields
- ✅ Single API key → 5 keys with rotation

**What Stayed:**
- ✅ Azure AI Search (vector database)
- ✅ Azure Blob Storage
- ✅ Azure Document Intelligence
- ✅ RAG architecture

**New Capabilities:**
- ✅ Intelligent form field detection
- ✅ Structured JSON responses
- ✅ Multi-select checkbox support
- ✅ Automatic API key failover

---

**Ready to use!** 🚀

For detailed documentation, see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
