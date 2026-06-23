# Project: OCR Plagiarism Detection Engine (Backend)

## 1. Project Context & Mission
This is the **Processing & Logic Layer** of a plagiarism detection system. It receives raw text extracted from images (via the Android app) and compares it against a database of known academic documents to calculate a similarity score.

The logic is based on **Information Processing Theory**: It must clean the input, retrieve knowledge, and output a decision.

## 2. Tech Stack Constraints
*   **OS:** Ubuntu (WSL 2) running on Windows.
*   **Language:** Python 3.10+.
*   **Framework:** FastAPI (for high-performance async handling).
*   **Server:** Uvicorn.
*   **Database:** SQLite (for prototyping) using SQLAlchemy.

## 3. NLP & Logic Libraries
*   **NLTK (Natural Language Toolkit):** For tokenization and stop-word removal.
*   **Scikit-Learn:** For `TfidfVectorizer` and `Cosine Similarity` (The core mathematical model for plagiarism).
*   **RapidFuzz:** For fuzzy string matching (handling OCR typos).

## 4. API Specification
The server must listen on `0.0.0.0` to be accessible from the Windows host/Android device.

### Endpoint: POST /api/analyze
**Request JSON:**
```json
{
  "student_id": "String",
  "text": "The raw text content extracted from the image..."
}
```

**What the analysis does:**

1. Cleans the submitted OCR text by lowercasing, removing punctuation/noise, tokenizing, removing stopwords, and dropping very short tokens.
2. Applies conservative fuzzy OCR correction and records every correction made.
3. Compares both raw-cleaned and corrected-cleaned text against a cached TF-IDF index of reference documents.
4. Combines TF-IDF, fuzzy token similarity, and phrase-overlap scores into one final score.
5. Adds reviewer evidence: shared phrases and suspicious sentence chunks.

**Important response fields:**

* `decision`: `High Probability of Plagiarism`, `Moderate Similarity Detected`, or `No Significant Match Found`.
* `highest_score`: The best final hybrid score across all reference documents.
* `word_count`: Cleaned word count kept for backward compatibility.
* `top_matches[].score`: Final hybrid score for a matched document.
* `top_matches[].tfidf_score`: TF-IDF cosine score after capping OCR correction boost.
* `top_matches[].raw_tfidf_score`: TF-IDF score before OCR correction.
* `top_matches[].corrected_tfidf_score`: TF-IDF score after OCR correction.
* `top_matches[].fuzzy_score`: RapidFuzz token-set similarity.
* `top_matches[].phrase_overlap_score`: Shared phrase overlap from 3- to 6-word phrases.
* `top_matches[].matched_phrases`: Shared phrases shown as reviewer evidence.
* `top_matches[].suspicious_chunks`: Submitted chunks and their closest reference chunks.
* `stats.documents_checked`: Number of reference documents compared.
* `stats.corrections`: OCR-style corrections applied before scoring.
* `stats.matched_chunk_count`: Number of suspicious chunks across returned matches.
* `stats.confidence_level`: Coarse match-strength label: `high`, `medium`, or `low`.
* `stats.thresholds`: Thresholds used for high/moderate/chunk decisions.
* `stats.score_weights`: Component weights used by the hybrid score.

The score is a repository similarity signal, not proof of intent. `No Significant Match Found`
means the text did not strongly match this app's current reference documents.
