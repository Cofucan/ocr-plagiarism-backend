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

    # Clean the input text
    cleaned_input = clean_text(input_text)

    # === LOGGING: Similarity Service ===
    logger.info(f"[SIMILARITY] Input text length: {len(input_text)} chars")
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
