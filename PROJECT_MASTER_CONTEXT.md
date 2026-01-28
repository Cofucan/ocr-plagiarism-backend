## 1. Executive Summary & Vision

**Project Title:** Mobile OCR-Based Plagiarism Detection System Using Image-Captured Documents.
**Case Study:** Federal University of Technology, Owerri (FUTO), Nigeria.

**The Problem:**
Traditional plagiarism tools (Turnitin, etc.) only work on digital files (Word/PDF). In Nigerian universities, a significant portion of student submissions (assignments, lab reports, quizzes) are **handwritten** or submitted as **printed hardcopies**. These physical documents currently bypass plagiarism checks, creating a loophole in academic integrity.

**The Solution:**
A mobile application that acts as a bridge between the physical and digital worlds. It captures an image of a physical document, extracts the text using Optical Character Recognition (OCR), and compares it against a repository of known academic works to detect similarity.

---

## 2. Theoretical Framework (The Logic)

The system is built on the **Information Processing Theory** (Input → Processing → Output).

1.  **Input (Sensory Memory):** The Mobile Camera captures the raw visual data.
2.  **Preprocessing (Selective Attention):** The app cleans the image (removes shadows, corrects skew) to focus only on the text.
3.  **Encoding (Short-term Memory):** OCR converts visual shapes into digital text strings.
4.  **Retrieval & Decision (Long-term Memory):** The Backend compares this string against the Database (Long-term memory) using vector similarity to judge originality.

---

## 3. System Architecture & Data Flow

### A. The Input Layer (Mobile App - Kotlin)

- **Role:** The "Eye" of the system.
- **Critical Challenge:** Document quality variability. Photos taken in dorm rooms often have bad lighting, shadows, or are taken at an angle.
- **The Workflow:**
    1.  User opens camera.
    2.  **Live Preview:** The user centers the document.
    3.  **Capture:** Image is frozen.
    4.  **OpenCV Preprocessing:**
        - _Grayscale:_ Remove color noise.
        - _Adaptive Thresholding:_ Force the image to black & white (Binarization) to separate ink from paper.
        - _Deskewing:_ (Optional) Straighten the text lines.
    5.  **OCR Extraction:** Google ML Kit scans the processed bitmap and returns a String.
    6.  **Transmission:** The raw text string is sent via JSON/HTTP to the backend.

### B. The Processing Layer (Backend API - Python)

- **Role:** The "Brain" of the system.
- **The Workflow:**
    1.  Receives JSON: `{"text": "The mitochondria is the powerhouse..."}`.
    2.  **NLP Cleaning:**
        - Lowercasing.
        - Removing "Stop Words" (is, the, and, at) using NLTK.
        - Removing special characters/punctuation.
    3.  **Vectorization (TF-IDF):** Converts the input text into a mathematical vector (a list of numbers representing word frequency).
    4.  **Similarity Check (Cosine Similarity):**
        - The system loads vectors of existing documents from the database.
        - It calculates the angle between the Input Vector and the Database Vectors.
        - **0.0** = No match. **1.0** = Exact copy.
    5.  **Decision Logic:**
        - If Similarity > 80%: "High Probability of Plagiarism".
        - If Similarity > 40%: "Moderate Similarity".
        - Else: "Original Content".

### C. The Storage Layer (Database)

- **Role:** The "Library" of known works.
- **Data:** Since we cannot scrape the whole internet, we simulate a **University Repository**.
- **Content:** The database will be seeded with sample text from:
    - Wikipedia articles (Science, Engineering).
    - Sample Thesis Abstracts.
    - Common textbook definitions.

---

## 4. Key Constraints & Requirements

### A. The "Nigerian Context" Constraints

1.  **Handwriting Recognition:** The system must not fail on cursive or messy handwriting.
    - _Tech Implication:_ This is why we use **Google ML Kit v2** (specialized for handwriting) instead of Tesseract (which struggles with it).
2.  **Data Economy:** Internet data is expensive.
    - _Tech Implication:_ **Do not upload images**. We process the image _on the phone_ and only upload the _text string_. This reduces payload size from 5MB (Image) to 2KB (Text).
3.  **Performance:**
    - Total turnaround time (Capture to Result) should be **< 5 seconds**.

### B. Development Environment Setup

- **Hardware:**
    - **Backend:** Running on WSL (Linux) inside Windows.
    - **Frontend:** Android Studio on Windows, connected to a physical Android device via USB.
- **Networking Bridge:**
    - The Python backend listens on `0.0.0.0`.
    - The Android phone connects via `ADB Reverse` (mapping phone port 8000 to PC port 8000).

---

## 5. Implementation Roadmap for AI Agents

### Phase 1: The Backend (The Engine)

- **Goal:** Create an API that can detect if two text strings are similar.
- **Task:** Setup FastAPI, install Scikit-Learn/NLTK, create the `CosineSimilarity` logic, and seed the database with 5-10 dummy documents.

### Phase 2: The Mobile Camera (The Eye)

- **Goal:** Take a picture and get a high-contrast bitmap.
- **Task:** Setup CameraX, create the `PreviewView`, and implement the Capture button.

### Phase 3: The Integrator (The Brain connection)

- **Goal:** Connect Phase 2 to Phase 1.
- **Task:** Implement OpenCV to clean the image, run ML Kit to extract text, and use Retrofit to send that text to the API created in Phase 1.

### Phase 4: The UI/UX

- **Goal:** Make it look academic and professional.
- **Task:** Display results with color codes (Red for plagiarism, Green for original). Show the source document name if plagiarism is found.
  """
