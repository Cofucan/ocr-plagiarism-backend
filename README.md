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
