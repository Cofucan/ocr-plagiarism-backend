# Crossref Integration Guide

## Overview

The system now supports **two-phase plagiarism detection**:

1. **Phase 1 (Local)**: Fast comparison against local database documents using TF-IDF + Cosine Similarity
2. **Phase 2 (External)**: Query Crossref's academic database for related published works

## New Endpoint

### POST `/api/analyze/external`

Queries Crossref for academic works related to the submitted text.

**Request:**
```json
{
  "student_id": "STU-2026-001",
  "text": "Your document text here..."
}
```

**Response:**
```json
{
  "student_id": "STU-2026-001",
  "query_keywords": ["machine", "learning", "neural", "networks", "deep"],
  "result_count": 10,
  "latency_seconds": 1.234,
  "sources": [
    {
      "source": "Crossref",
      "doi": "10.1234/example.doi",
      "title": "Deep Learning in Computer Vision",
      "authors": ["John Doe", "Jane Smith"],
      "year": 2024,
      "abstract_snippet": "This paper presents...",
      "score": 0.85,
      "url": "https://doi.org/10.1234/example.doi",
      "publisher": "IEEE"
    }
  ]
}
```

## Configuration

Update these settings in `app/config.py` or `.env`:

```python
CROSSREF_BASE_URL = "https://api.crossref.org"
CROSSREF_MAILTO = "your.email@university.edu"  # REQUIRED for API etiquette
CROSSREF_TIMEOUT = 15  # seconds
CROSSREF_MAX_RESULTS = 10
CROSSREF_MAX_KEYWORDS = 10
CROSSREF_MIN_TOKEN_LEN = 3
CROSSREF_SNIPPET_LEN = 400  # characters
```

⚠️ **Important**: Set a valid email for `CROSSREF_MAILTO` to comply with Crossref's API etiquette policy.

## Two-Phase Workflow

### Option 1: Sequential Calls (Recommended)

```python
# Phase 1: Fast local check
response1 = await client.post("/api/analyze", json={
    "student_id": "STU-001",
    "text": document_text
})
# Returns immediately with local matches

# Phase 2: External sources (if needed)
response2 = await client.post("/api/analyze/external", json={
    "student_id": "STU-001",
    "text": document_text
})
# Returns Crossref results with latency tracking
```

### Option 2: Parallel Calls

```python
import asyncio

results = await asyncio.gather(
    client.post("/api/analyze", json=payload),
    client.post("/api/analyze/external", json=payload)
)
local_results, external_results = results
```

## Features

### 1. Keyword Extraction
- Uses frequency-based ranking from existing NLP cleaning
- Configurable limits (default: top 10 keywords)
- Filters short tokens and stopwords

### 2. In-Memory Caching
- Caches Crossref results for 1 hour
- Reduces API calls and improves response time
- Suitable for educational projects

### 3. Latency Tracking
- Measures and reports query time
- Useful for performance analysis in your thesis
- Shows cache effectiveness

### 4. Abstract Snippets
- Returns truncated abstracts (default: 400 chars)
- Strips HTML tags for clean display
- Handles missing abstracts gracefully

## Testing

Run the test script:

```bash
cd /home/cofucan/dev/OCR_Plagiarism_System/BackendServer
python test_crossref.py
```

Or test via the API:

```bash
# Start the server
uvicorn app.main:app --reload

# Test the endpoint
curl -X POST http://localhost:8000/api/analyze/external \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "TEST-001",
    "text": "Machine learning is a subset of artificial intelligence..."
  }'
```

## Educational Considerations

### For Your Masters Thesis

1. **Performance Comparison**: Track and compare latency between local and external checks
2. **Accuracy Analysis**: Compare local similarity scores vs. Crossref relevance scores
3. **Coverage**: Document the types of documents found in Crossref vs. local database
4. **Limitations**: Discuss API rate limits, network dependency, and cache strategies

### Simple Architecture Benefits

- No external dependencies beyond httpx
- No persistent cache database needed
- Easy to understand and extend
- Compliant with academic API usage policies

## Troubleshooting

### Import Error: `httpx` not found
```bash
pip install httpx==0.28.1
```

### HTTP 502: Service Unavailable
- Check internet connection
- Verify `CROSSREF_MAILTO` is set to a valid email
- Check Crossref API status: https://status.crossref.org/

### Empty Results
- Text may be too short (minimum 5 words)
- Keywords may not match academic content
- Try more technical/academic terminology

## API Rate Limits

Crossref is free and has generous limits:
- **Rate limit**: ~50 requests/second (unofficial)
- **No authentication required** (just provide mailto)
- **Polite pool**: Setting mailto gives higher priority

The in-memory cache helps avoid hitting rate limits during testing.

## Next Steps

1. ✅ Set valid `CROSSREF_MAILTO` in config
2. ✅ Test the endpoint with sample text
3. ✅ Integrate into your Android app
4. ✅ Document findings in your thesis
5. Consider adding other free sources (arXiv, PubMed Central)

## Example Response Times

- **Local analysis**: ~100-500ms (fast, no network)
- **Crossref (first call)**: ~1-3 seconds (network + API)
- **Crossref (cached)**: ~5-50ms (in-memory lookup)

This demonstrates the value of the two-phase approach!
