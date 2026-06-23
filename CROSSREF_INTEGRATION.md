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

## Response Properties Explained

### Top-Level Fields

| Property | Type | Description |
|----------|------|-------------|
| `student_id` | string | Echo of the student ID from the request. Used for tracking and logging which student submitted the text. |
| `query_keywords` | array[string] | The top keywords extracted from the submitted text using frequency-based ranking. These are the terms used to search Crossref. Useful for understanding how the system interpreted the document's main topics. |
| `result_count` | integer | Total number of sources found in Crossref matching the query keywords. Ranges from 0 to `CROSSREF_MAX_RESULTS` (default: 10). |
| `latency_seconds` | number | Time taken (in seconds) to complete the Crossref query. First calls: 1-3 seconds. Cached calls: <50ms. Useful for measuring API performance and cache effectiveness. |
| `sources` | array[object] | Array of academic sources found in Crossref. Each object contains metadata about a published work. See below for individual source field descriptions. |

### Source Object Fields (within `sources` array)

| Property | Type | Description |
|----------|------|-------------|
| `source` | string | Database identifier. Currently always `"Crossref"` (extensible for future API sources like arXiv, PubMed). |
| `doi` | string or null | Digital Object Identifier - a unique persistent identifier for academic publications. Example: `10.1234/example.doi`. Can be looked up at https://doi.org/{doi}. `null` if not available. |
| `title` | string or null | Full title of the published work. Used for identifying the exact paper. `null` if metadata missing. |
| `authors` | array[string] | List of author names extracted from the publication metadata. Empty array `[]` if no authors found (some publications don't have author details in Crossref). Helps verify authorship and identify co-authors. |
| `year` | integer or null | Publication year. Useful for determining how recent the source is. `null` if publication date not available in Crossref. |
| `abstract_snippet` | string or null | Truncated abstract (max 400 characters by default) from the paper. Provides context about the paper's content. Stripped of HTML tags for clean display. `null` if no abstract available in Crossref. |
| `score` | number or null | Crossref's relevance score normalized to 0.0-1.0 range. Higher score = more relevant to the query keywords. Example: `1.0` = perfect match, `0.5` = moderate match. Helps instructors assess how closely the source matches the submitted text. `null` if score unavailable. |
| `url` | string or null | Direct link to the paper's DOI resolver: https://doi.org/{doi}. Click this to view or download the actual paper. `null` if no URL available. |
| `publisher` | string or null | Publishing organization (e.g., IEEE, Elsevier, ACM). Indicates the credibility and authority of the source. Useful for academic context analysis. `null` if publisher info unavailable. |
| `plagiarism_score` | number or null | **NEW: N-gram based plagiarism detection vs. abstract (0.0-1.0)**. Calculated by comparing the student's text against the paper's abstract snippet using trigram (3-word) matching. Higher = more text overlap detected. `null` if abstract unavailable (cannot calculate plagiarism score). |

### Example Interpretation

```json
{
  "student_id": "STU-2026-001",
  "query_keywords": ["neural", "networks", "learning", "deep"],
  "result_count": 10,
  "latency_seconds": 2.134,
  "sources": [
    {
      "source": "Crossref",
      "doi": "10.1201/b22400-15",
      "title": "Neural Networks and Deep Learning",
      "authors": ["Richard E. Neapolitan", "Xia Jiang"],
      "year": 2018,
      "abstract_snippet": "Neural networks are a powerful machine learning technique that has been applied to many domains...",
      "score": 0.862,
      "url": "https://doi.org/10.1201/b22400-15",
      "publisher": "Chapman and Hall/CRC",
      "plagiarism_score": 0.42
    }
  ]
}
```

**Complete Interpretation:**
- **Relevance Score (0.862)**: This paper is **highly relevant** to the student's topic (strong keyword match)
- **Plagiarism Score (0.42)**: The student's text has **moderate overlap** with the abstract (potential paraphrasing or common terminology)
- **Combined Assessment**:
  - ✓ Student is writing about the right topic
  - ⚠️ Some text similarity detected - verify if properly cited
  - 📎 Use the DOI to access full paper and check for word-for-word plagiarism
- **Next Step**: Instructor should click the DOI link to verify the citation status

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

## Understanding the Results

### Plagiarism Score Interpretation (**NEW**)

The `plagiarism_score` field (0.0-1.0) indicates the level of **n-gram overlap** between the student's text and the paper's abstract:

| Score Range | Interpretation | Action |
|------------|-----------------|--------|
| **0.0-0.15** | Minimal overlap | Very unlikely to be plagiarism. Normal academic writing may use field terminology. |
| **0.15-0.35** | Moderate overlap | Potential source but low plagiarism concern. Student may have paraphrased or cited. |
| **0.35-0.60** | High overlap | **Flag for review.** Significant text similarity detected. Verify if student cited the source. |
| **0.60-0.80** | Very high overlap | **Strong plagiarism indicator.** Large portions of text match abstract. Likely unattributed copying. |
| **0.80-1.0** | Near exact match | **Critical plagiarism.** Text appears to be copied directly from abstract with minimal paraphrasing. |
| **N/A** | No abstract available | Cannot calculate plagiarism score. Requires accessing full paper text (beyond scope of this tool). |

**Example Interpretation:**
- Student submits: "Machine learning neural networks enable computers to learn from data"
- Crossref abstract excerpt: "neural networks enable systems to learn from experience without explicit programming"
- `plagiarism_score`: ~0.45 (moderate overlap due to shared phrases)
- **Action**: Investigate further; may be legitimate citation or paraphrasing

### How Plagiarism Score is Calculated

The system uses **trigram matching** (3-word sequences):

```python
1. Clean both texts (remove stopwords, lowercase, tokenize)
2. Extract all 3-word sequences (trigrams) from both texts
3. Find common trigrams between student text and abstract
4. Calculate Jaccard similarity: (intersection ∩ union) / union
5. Return score 0.0-1.0
```

**Example:**
```
Student text: "deep learning networks process data efficiently"
Abstract:     "deep learning techniques process information quickly"

Trigrams in student text:
  ["deep", "learning", "networks"]
  ["learning", "networks", "process"]
  ["networks", "process", "data"]
  ["process", "data", "efficiently"]

Trigrams in abstract:
  ["deep", "learning", "techniques"]
  ["learning", "techniques", "process"]
  ["techniques", "process", "information"]
  ["process", "information", "quickly"]

Common trigrams: ["process"] (at index level, not full match)
Jaccard = 1/7 = 0.14 → Low plagiarism concern
```

### Limitations of Abstract-Based Detection

⚠️ **Important:** This plagiarism detection has limitations:

1. **Abstract-only matching**: Only compares against ~400-char abstracts, not full papers
2. **Paraphrasing:** Detects word/phrase overlap but misses sophisticated paraphrasing
3. **Domain terminology:** Technical fields have common terms (e.g., "neural networks") that naturally appear in multiple papers
4. **No semantic understanding:** Doesn't understand meaning, only n-gram patterns

**For Full Plagiarism Detection:**
- Use the local database check (`/api/analyze`) for reference documents
- For comprehensive checking, manually verify flagged papers via DOI links
- For institutional grade plagiarism detection, integrate Turnitin API (paid)

### Score Interpretation

The `score` field (0.0-1.0) indicates how relevant each Crossref result is to the submitted text:

| Score Range | Interpretation | Use Case |
|------------|-----------------|----------|
| **0.9-1.0** | Highly relevant | Direct match or very similar topic. Strong indicator of potential plagiarism if text is identical. |
| **0.7-0.89** | Very relevant | Related scholarly work. Good reference for comparison. Student should cite if used. |
| **0.5-0.69** | Relevant | Somewhat related to the topic. May share keywords but different focus. |
| **0.0-0.49** | Marginally relevant | Weak match. Included in results due to keyword overlap. Less concern for plagiarism. |

### Keywords Analysis

The `query_keywords` array shows how the system understood the main topics:

**Good indicators (relevant keywords extracted):**
- Technical terms: "neural", "networks", "deep", "learning"
- Avoid: common words like "system", "data"

**What it reveals:**
- Which concepts dominate the student's text
- Whether the submission focuses on main topic or tangential areas
- Quality of OCR (for physical document submissions)

### Latency Insights

The `latency_seconds` field has educational value:

- **2-3 seconds** (network call): Shows real API latency
- **<50ms** (cached): Demonstrates caching effectiveness
- **>5 seconds**: May indicate network issues or Crossref slowness

**For your thesis:** Track latency across multiple queries to show:
- Average API response time
- Cache hit rate improvement
- Cost-effectiveness of caching strategy

### DOI and URL Fields

The `doi` and `url` fields enable verification:

1. **Click the URL** to access the actual paper source
2. **Verify publication details** match Crossref records
3. **Check academic legitimacy** by publisher reputation
4. **Enable detailed plagiarism checking** if needed (detect copy-paste vs. paraphrasing)

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
