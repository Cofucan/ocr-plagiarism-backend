"""
Fuzzy matching service for OCR error correction.
Uses RapidFuzz to correct misspelled words before similarity comparison.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document

# Configure logging
logger = logging.getLogger(__name__)

# Minimum word length to attempt correction (short words have too many false matches)
MIN_WORD_LENGTH = 4


@dataclass
class Correction:
    """A single OCR-style correction made to the submitted text."""

    original: str
    corrected: str
    confidence: float


@dataclass
class CorrectionResult:
    """Corrected text plus metadata about OCR corrections."""

    text: str
    corrections: list[Correction]

    @property
    def corrections_made(self) -> int:
        return len(self.corrections)


@lru_cache(maxsize=1)
def _get_cached_vocabulary_key() -> int:
    """Returns a cache key that can be invalidated when vocabulary changes."""
    return id(_get_cached_vocabulary_key)


def build_vocabulary(db: Session) -> set[str]:
    """
    Build a vocabulary of known words from all documents in the database.

    Args:
        db: Database session

    Returns:
        Set of unique words from all documents
    """
    documents = db.query(Document).all()
    vocabulary = set()

    for doc in documents:
        # Extract words from content (simple tokenization)
        words = doc.content.lower().split()
        for word in words:
            # Clean the word: keep only alphanumeric characters
            cleaned = ''.join(c for c in word if c.isalnum())
            if len(cleaned) >= MIN_WORD_LENGTH:
                vocabulary.add(cleaned)

        # Also add words from title
        title_words = doc.title.lower().split()
        for word in title_words:
            cleaned = ''.join(c for c in word if c.isalnum())
            if len(cleaned) >= MIN_WORD_LENGTH:
                vocabulary.add(cleaned)

    logger.info(f"[FUZZY] Built vocabulary with {len(vocabulary)} unique words")
    return vocabulary


def correct_word(word: str, vocabulary: set[str]) -> str:
    """
    Attempt to correct a single word using fuzzy matching against the vocabulary.

    Args:
        word: The potentially misspelled word
        vocabulary: Set of known correct words

    Returns:
        The corrected word, or the original if no good match found
    """
    if not word or len(word) < MIN_WORD_LENGTH:
        return word

    # If word is already in vocabulary, no correction needed
    if word in vocabulary:
        return word

    # Find the best match in vocabulary
    result = process.extractOne(
        word,
        vocabulary,
        scorer=fuzz.ratio,
        score_cutoff=settings.FUZZY_CORRECTION_THRESHOLD,
    )

    if result:
        match, score, _ = result
        logger.debug(f"[FUZZY] Corrected '{word}' -> '{match}' (score: {score})")
        return match

    return word


def correct_word_with_score(
    word: str,
    vocabulary: set[str],
) -> tuple[str, float | None]:
    """Correct one word and return the confidence score when corrected."""
    if not word or len(word) < MIN_WORD_LENGTH:
        return word, None

    if word in vocabulary:
        return word, None

    result = process.extractOne(
        word,
        vocabulary,
        scorer=fuzz.ratio,
        score_cutoff=settings.FUZZY_CORRECTION_THRESHOLD,
    )

    if result:
        match, score, _ = result
        logger.debug(f"[FUZZY] Corrected '{word}' -> '{match}' (score: {score})")
        return match, float(score)

    return word, None


def correct_text_with_stats(text: str, db: Session) -> CorrectionResult:
    """
    Correct OCR errors in text using fuzzy matching against document vocabulary.

    Args:
        text: The OCR text with potential errors
        db: Database session

    Returns:
        Text with corrected words and correction metadata
    """
    if not text:
        return CorrectionResult(text=text, corrections=[])

    # Build vocabulary from database
    vocabulary = build_vocabulary(db)

    if not vocabulary:
        logger.warning("[FUZZY] Empty vocabulary, skipping correction")
        return CorrectionResult(text=text, corrections=[])

    # Tokenize and correct each word
    words = text.lower().split()
    corrected_words = []
    corrections: list[Correction] = []

    for word in words:
        # Preserve non-alphanumeric parts
        cleaned = ''.join(c for c in word if c.isalnum())

        if len(cleaned) >= MIN_WORD_LENGTH:
            corrected, confidence = correct_word_with_score(cleaned, vocabulary)
            if corrected != cleaned:
                corrections.append(
                    Correction(
                        original=cleaned,
                        corrected=corrected,
                        confidence=confidence or 0.0,
                    )
                )
            corrected_words.append(corrected)
        else:
            corrected_words.append(cleaned)

    corrected_text = ' '.join(corrected_words)

    logger.info(f"[FUZZY] Made {len(corrections)} corrections out of {len(words)} words")
    logger.info(f"[FUZZY] Corrected text preview: {corrected_text[:150]!r}")

    return CorrectionResult(text=corrected_text, corrections=corrections)


def correct_text(text: str, db: Session) -> str:
    """Backward-compatible helper that returns corrected text only."""
    return correct_text_with_stats(text, db).text
