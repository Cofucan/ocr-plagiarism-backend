"""
Fuzzy matching service for OCR error correction.
Uses RapidFuzz to correct misspelled words before similarity comparison.
"""

import logging
from functools import lru_cache

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.models import Document

# Configure logging
logger = logging.getLogger(__name__)

# Minimum similarity threshold for fuzzy matching (0-100)
FUZZY_THRESHOLD = 70

# Minimum word length to attempt correction (short words have too many false matches)
MIN_WORD_LENGTH = 4


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
        score_cutoff=FUZZY_THRESHOLD,
    )

    if result:
        match, score, _ = result
        logger.debug(f"[FUZZY] Corrected '{word}' -> '{match}' (score: {score})")
        return match

    return word


def correct_text(text: str, db: Session) -> str:
    """
    Correct OCR errors in text using fuzzy matching against document vocabulary.

    Args:
        text: The OCR text with potential errors
        db: Database session

    Returns:
        Text with corrected words
    """
    if not text:
        return text

    # Build vocabulary from database
    vocabulary = build_vocabulary(db)

    if not vocabulary:
        logger.warning("[FUZZY] Empty vocabulary, skipping correction")
        return text

    # Tokenize and correct each word
    words = text.lower().split()
    corrected_words = []
    corrections_made = 0

    for word in words:
        # Preserve non-alphanumeric parts
        cleaned = ''.join(c for c in word if c.isalnum())

        if len(cleaned) >= MIN_WORD_LENGTH:
            corrected = correct_word(cleaned, vocabulary)
            if corrected != cleaned:
                corrections_made += 1
            corrected_words.append(corrected)
        else:
            corrected_words.append(cleaned)

    corrected_text = ' '.join(corrected_words)

    logger.info(f"[FUZZY] Made {corrections_made} corrections out of {len(words)} words")
    logger.info(f"[FUZZY] Corrected text preview: {corrected_text[:150]!r}")

    return corrected_text
