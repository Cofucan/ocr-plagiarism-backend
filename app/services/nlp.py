"""
NLP preprocessing service for text cleaning.
Prepares text for TF-IDF vectorization by removing noise.
"""

import re
import string

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


# Cache stopwords for performance
try:
    STOP_WORDS = set(stopwords.words("english"))
except LookupError:
    # If NLTK data not downloaded, use a minimal set
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "under",
        "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "and", "but", "if", "or", "because", "until",
        "while", "this", "that", "these", "those", "it", "its", "i", "me",
        "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself",
        "she", "her", "hers", "herself", "they", "them", "their", "theirs",
        "themselves", "what", "which", "who", "whom", "about", "against",
    }


def clean_text(text: str) -> str:
    """
    Clean and preprocess text for similarity comparison.

    Pipeline:
        1. Convert to lowercase
        2. Remove special characters and punctuation
        3. Remove extra whitespace
        4. Tokenize
        5. Remove stopwords
        6. Rejoin tokens

    Args:
        text: Raw input text (possibly from OCR)

    Returns:
        Cleaned text ready for TF-IDF vectorization
    """
    if not text or not isinstance(text, str):
        return ""

    # Step 1: Lowercase
    text = text.lower()

    # Step 2: Remove special characters (keep only letters, numbers, spaces)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Step 3: Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Step 4 & 5: Tokenize and remove stopwords
    try:
        tokens = word_tokenize(text)
    except LookupError:
        # Fallback if punkt tokenizer not available
        tokens = text.split()

    # Remove stopwords and short tokens (likely noise from OCR)
    cleaned_tokens = [
        token for token in tokens
        if token not in STOP_WORDS and len(token) > 2
    ]

    # Step 6: Rejoin
    return " ".join(cleaned_tokens)


def get_word_count(text: str) -> int:
    """Get the word count of cleaned text."""
    cleaned = clean_text(text)
    if not cleaned:
        return 0
    return len(cleaned.split())
