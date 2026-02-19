"""
Similarity detection service using TF-IDF and Cosine Similarity.
Core plagiarism detection logic.
"""

import logging
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.services.nlp import clean_text
from app.services.fuzzy import correct_text

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Represents a similarity match with a reference document."""

    document_id: int
    title: str
    category: str
    source: str | None
    similarity_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "category": self.category,
            "source": self.source,
            "score": round(self.similarity_score, 4),
        }


def find_top_matches(
    input_text: str,
    db: Session,
    top_n: int | None = None,
) -> list[MatchResult]:
    """
    Find the top N most similar documents to the input text.

    Uses TF-IDF vectorization and cosine similarity to compare
    the input against all documents in the repository.

    Args:
        input_text: The raw text to check for plagiarism
        db: Database session
        top_n: Number of top matches to return (default from settings)

    Returns:
        List of MatchResult objects sorted by similarity (highest first)
    """
    if top_n is None:
        top_n = settings.TOP_MATCHES_COUNT

    # === Step 1: Fuzzy correction for OCR errors ===
    logger.info("[SIMILARITY] Applying fuzzy correction for OCR errors...")
    corrected_input = correct_text(input_text, db)

    # === Step 2: Clean the corrected text ===
    cleaned_input = clean_text(corrected_input)

    # === LOGGING: Similarity Service ===
    logger.info(f"[SIMILARITY] Original input length: {len(input_text)} chars")
    logger.info(f"[SIMILARITY] After fuzzy correction: {len(corrected_input)} chars")
    logger.info(f"[SIMILARITY] Cleaned input length: {len(cleaned_input)} chars")
    logger.info(f"[SIMILARITY] Cleaned input preview: {cleaned_input[:150]!r}")

    if not cleaned_input:
        logger.warning("[SIMILARITY] Cleaned input is empty! Returning no matches.")
        return []

    # Fetch all reference documents from the database
    documents = db.query(Document).all()
    logger.info(f"[SIMILARITY] Found {len(documents)} documents in database")

    if not documents:
        logger.warning("[SIMILARITY] No documents in database! Returning no matches.")
        return []

    # Prepare corpus: input text + all document contents
    corpus = [cleaned_input] + [clean_text(doc.content) for doc in documents]

    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer(
        max_features=5000,  # Limit features for performance
        ngram_range=(1, 2),  # Use unigrams and bigrams
        min_df=1,  # Minimum document frequency
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        logger.info(f"[SIMILARITY] TF-IDF matrix shape: {tfidf_matrix.shape}")
    except ValueError as e:
        # Empty vocabulary (no valid tokens)
        logger.error(f"[SIMILARITY] TF-IDF failed: {e}")
        return []

    # Calculate cosine similarity between input (index 0) and all documents
    input_vector = tfidf_matrix[0:1]  # Keep as sparse matrix
    document_vectors = tfidf_matrix[1:]  # All reference documents

    similarities = cosine_similarity(input_vector, document_vectors).flatten()

    # Create match results with similarity scores
    matches = []
    for idx, doc in enumerate(documents):
        matches.append(
            MatchResult(
                document_id=doc.id,
                title=doc.title,
                category=doc.category,
                source=doc.source,
                similarity_score=float(similarities[idx]),
            )
        )

    # Sort by similarity (highest first) and return top N
    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    return matches[:top_n]


def get_decision(highest_score: float) -> str:
    """
    Determine the plagiarism verdict based on the highest similarity score.

    Args:
        highest_score: The highest cosine similarity score (0.0 to 1.0)

    Returns:
        Human-readable decision string
    """
    if highest_score >= settings.PLAGIARISM_THRESHOLD_HIGH:
        return "High Probability of Plagiarism"
    elif highest_score >= settings.PLAGIARISM_THRESHOLD_MODERATE:
        return "Moderate Similarity Detected"
    else:
        return "Original Content"


def get_decision_color(decision: str) -> str:
    """
    Get the color code for the decision (for UI display).

    Returns:
        Color string: "red", "yellow", or "green"
    """
    if "High" in decision:
        return "red"
    elif "Moderate" in decision:
        return "yellow"
    else:
        return "green"


def calculate_ngram_similarity(text1: str, text2: str, n: int = 3) -> float:
    """
    Calculate n-gram based plagiarism similarity between two texts.

    Uses token-level n-grams (not character-level) for robustness against
    minor variations in punctuation and whitespace.

    Args:
        text1: Student's text (should be cleaned)
        text2: Reference text/abstract (should be cleaned)
        n: Size of n-gram (default 3 = trigrams)

    Returns:
        Plagiarism score (0.0 to 1.0) based on n-gram overlap
    """
    if not text1 or not text2:
        return 0.0

    # Tokenize by splitting on whitespace
    tokens1 = text1.split()
    tokens2 = text2.split()

    if len(tokens1) < n or len(tokens2) < n:
        return 0.0

    # Generate n-grams (sequences of n tokens)
    ngrams1 = set(tuple(tokens1[i:i + n]) for i in range(len(tokens1) - n + 1))
    ngrams2 = set(tuple(tokens2[i:i + n]) for i in range(len(tokens2) - n + 1))

    if not ngrams1 or not ngrams2:
        return 0.0

    # Calculate Jaccard similarity (intersection / union)
    intersection = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)

    similarity = intersection / union if union > 0 else 0.0
    return min(similarity, 1.0)  # Ensure 0.0-1.0 range
