"""
Similarity detection service.

The detector combines cached TF-IDF cosine similarity, fuzzy full-text similarity,
phrase overlap, and sentence-chunk evidence. TF-IDF remains the main signal, while
the extra signals make OCR-heavy and partial-copy cases easier to inspect.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.services.fuzzy import Correction, correct_text_with_stats
from app.services.nlp import clean_text

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ChunkMatch:
    """A suspicious submitted text chunk and its closest reference document chunk."""

    input_chunk: str
    matched_chunk: str
    score: float


@dataclass
class MatchResult:
    """Represents a similarity match with a reference document."""

    document_id: int
    title: str
    category: str
    source: str | None
    similarity_score: float
    tfidf_score: float
    fuzzy_score: float
    phrase_overlap_score: float
    raw_tfidf_score: float
    corrected_tfidf_score: float
    matched_phrases: list[str] = field(default_factory=list)
    suspicious_chunks: list[ChunkMatch] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "category": self.category,
            "source": self.source,
            "score": round(self.similarity_score, 4),
            "tfidf_score": round(self.tfidf_score, 4),
            "fuzzy_score": round(self.fuzzy_score, 4),
            "phrase_overlap_score": round(self.phrase_overlap_score, 4),
            "raw_tfidf_score": round(self.raw_tfidf_score, 4),
            "corrected_tfidf_score": round(self.corrected_tfidf_score, 4),
            "matched_phrases": self.matched_phrases,
            "suspicious_chunks": [
                {
                    "input_chunk": chunk.input_chunk,
                    "matched_chunk": chunk.matched_chunk,
                    "score": round(chunk.score, 4),
                }
                for chunk in self.suspicious_chunks
            ],
        }


@dataclass
class AnalysisMetadata:
    """Non-match stats from an analysis run."""

    raw_word_count: int
    cleaned_word_count: int
    corrected_word_count: int
    documents_checked: int
    corrections_made: int
    corrections: list[Correction]
    matched_chunk_count: int
    confidence_level: str
    analysis_method: str
    thresholds: dict[str, float]
    score_weights: dict[str, float]


@dataclass
class SimilarityAnalysis:
    """Full internal result from plagiarism analysis."""

    matches: list[MatchResult]
    metadata: AnalysisMetadata


@dataclass
class IndexedDocument:
    """Preprocessed representation of a reference document."""

    document: Document
    cleaned_content: str
    chunks: list[str]
    phrase_sets: dict[int, set[str]]


@dataclass
class DocumentIndex:
    """Cached TF-IDF index for the current set of reference documents."""

    signature: str
    documents: list[IndexedDocument]
    vectorizer: TfidfVectorizer
    tfidf_matrix: object


_DOCUMENT_INDEX: DocumentIndex | None = None


def find_top_matches(
    input_text: str,
    db: Session,
    top_n: int | None = None,
) -> list[MatchResult]:
    """
    Find the top N most similar documents to the input text.

    This wrapper preserves the previous service API. Use ``analyze_similarity`` when
    correction stats, thresholds, and analysis metadata are also needed.
    """
    return analyze_similarity(input_text=input_text, db=db, top_n=top_n).matches


def analyze_similarity(
    input_text: str,
    db: Session,
    top_n: int | None = None,
) -> SimilarityAnalysis:
    """
    Analyze submitted text against the reference repository.

    The final score is a weighted hybrid:
    - TF-IDF cosine similarity, capped so OCR correction cannot over-boost it
    - RapidFuzz token-set similarity
    - Shared phrase overlap
    """
    if top_n is None:
        top_n = settings.TOP_MATCHES_COUNT

    raw_word_count = len(re.findall(r"\b\w+\b", input_text or ""))
    raw_cleaned_input = clean_text(input_text)

    logger.info("[SIMILARITY] Applying fuzzy correction for OCR errors...")
    correction_result = correct_text_with_stats(input_text, db)
    corrected_input = correction_result.text
    corrected_cleaned_input = clean_text(corrected_input)

    logger.info(f"[SIMILARITY] Original input length: {len(input_text)} chars")
    logger.info(f"[SIMILARITY] After fuzzy correction: {len(corrected_input)} chars")
    logger.info(f"[SIMILARITY] Cleaned input length: {len(corrected_cleaned_input)} chars")
    logger.info(f"[SIMILARITY] Cleaned input preview: {corrected_cleaned_input[:150]!r}")

    metadata = AnalysisMetadata(
        raw_word_count=raw_word_count,
        cleaned_word_count=len(raw_cleaned_input.split()) if raw_cleaned_input else 0,
        corrected_word_count=len(corrected_cleaned_input.split()) if corrected_cleaned_input else 0,
        documents_checked=0,
        corrections_made=correction_result.corrections_made,
        corrections=correction_result.corrections,
        matched_chunk_count=0,
        confidence_level="low",
        analysis_method=(
            "cached_tfidf_cosine_with_fuzzy_phrase_overlap_and_chunk_evidence"
        ),
        thresholds={
            "high": settings.PLAGIARISM_THRESHOLD_HIGH,
            "moderate": settings.PLAGIARISM_THRESHOLD_MODERATE,
            "suspicious_chunk": settings.SUSPICIOUS_CHUNK_THRESHOLD,
        },
        score_weights={
            "tfidf": settings.TFIDF_WEIGHT,
            "fuzzy": settings.FUZZY_WEIGHT,
            "phrase": settings.PHRASE_WEIGHT,
        },
    )

    if not corrected_cleaned_input:
        logger.warning("[SIMILARITY] Cleaned input is empty! Returning no matches.")
        return SimilarityAnalysis(matches=[], metadata=metadata)

    index = get_document_index(db)
    metadata.documents_checked = len(index.documents)

    if not index.documents:
        logger.warning("[SIMILARITY] No documents in database! Returning no matches.")
        return SimilarityAnalysis(matches=[], metadata=metadata)

    raw_tfidf_scores = _tfidf_scores(raw_cleaned_input, index)
    corrected_tfidf_scores = _tfidf_scores(corrected_cleaned_input, index)
    input_phrase_sets = {
        n: _ngrams(corrected_cleaned_input, n)
        for n in range(3, 7)
    }
    input_chunks = _chunk_text(input_text)

    matches = []
    for idx, indexed_doc in enumerate(index.documents):
        raw_tfidf_score = raw_tfidf_scores[idx]
        corrected_tfidf_score = corrected_tfidf_scores[idx]
        capped_tfidf_score = min(
            corrected_tfidf_score,
            raw_tfidf_score + settings.OCR_MAX_SCORE_BOOST,
        )
        fuzzy_score = fuzz.token_set_ratio(
            corrected_cleaned_input,
            indexed_doc.cleaned_content,
        ) / 100
        phrase_overlap_score = _phrase_overlap_score(
            input_phrase_sets,
            indexed_doc.phrase_sets,
        )
        similarity_score = _weighted_score(
            tfidf_score=capped_tfidf_score,
            fuzzy_score=fuzzy_score,
            phrase_overlap_score=phrase_overlap_score,
        )

        matches.append(
            MatchResult(
                document_id=indexed_doc.document.id,
                title=indexed_doc.document.title,
                category=indexed_doc.document.category,
                source=indexed_doc.document.source,
                similarity_score=similarity_score,
                tfidf_score=capped_tfidf_score,
                fuzzy_score=fuzzy_score,
                phrase_overlap_score=phrase_overlap_score,
                raw_tfidf_score=raw_tfidf_score,
                corrected_tfidf_score=corrected_tfidf_score,
                matched_phrases=_matched_phrases(
                    input_phrase_sets,
                    indexed_doc.phrase_sets,
                ),
                suspicious_chunks=_suspicious_chunks(input_chunks, indexed_doc.chunks),
            )
        )

    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    top_matches = matches[:top_n]
    highest_score = top_matches[0].similarity_score if top_matches else 0.0
    metadata.confidence_level = _confidence_level(highest_score)
    metadata.matched_chunk_count = sum(
        len(match.suspicious_chunks)
        for match in top_matches
    )
    return SimilarityAnalysis(matches=top_matches, metadata=metadata)


def get_decision(highest_score: float) -> str:
    """
    Determine the plagiarism verdict based on the highest similarity score.

    Args:
        highest_score: The highest similarity score (0.0 to 1.0)

    Returns:
        Human-readable decision string
    """
    if highest_score >= settings.PLAGIARISM_THRESHOLD_HIGH:
        return "High Probability of Plagiarism"
    elif highest_score >= settings.PLAGIARISM_THRESHOLD_MODERATE:
        return "Moderate Similarity Detected"
    else:
        return "No Significant Match Found"


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


def _confidence_level(highest_score: float) -> str:
    """Return a coarse confidence label for the strongest repository match."""
    if highest_score >= settings.PLAGIARISM_THRESHOLD_HIGH:
        return "high"
    if highest_score >= settings.PLAGIARISM_THRESHOLD_MODERATE:
        return "medium"
    return "low"


def get_document_index(db: Session) -> DocumentIndex:
    """Return a cached TF-IDF index, rebuilding when reference documents change."""
    global _DOCUMENT_INDEX

    documents = db.query(Document).order_by(Document.id).all()
    signature = _documents_signature(documents)

    if _DOCUMENT_INDEX and _DOCUMENT_INDEX.signature == signature:
        logger.info("[SIMILARITY] Reusing cached document index")
        return _DOCUMENT_INDEX

    logger.info(f"[SIMILARITY] Building document index for {len(documents)} documents")
    indexed_documents = [
        IndexedDocument(
            document=doc,
            cleaned_content=clean_text(doc.content),
            chunks=_chunk_text(doc.content),
            phrase_sets={n: _ngrams(clean_text(doc.content), n) for n in range(3, 7)},
        )
        for doc in documents
    ]
    corpus = [indexed_doc.cleaned_content for indexed_doc in indexed_documents]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=1,
    )

    if any(corpus):
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            logger.info(f"[SIMILARITY] TF-IDF matrix shape: {tfidf_matrix.shape}")
        except ValueError as e:
            logger.error(f"[SIMILARITY] TF-IDF failed: {e}")
            tfidf_matrix = None
    else:
        tfidf_matrix = None

    _DOCUMENT_INDEX = DocumentIndex(
        signature=signature,
        documents=indexed_documents,
        vectorizer=vectorizer,
        tfidf_matrix=tfidf_matrix,
    )
    return _DOCUMENT_INDEX


def clear_document_index_cache() -> None:
    """Clear the in-process document index cache. Useful for tests/admin tasks."""
    global _DOCUMENT_INDEX
    _DOCUMENT_INDEX = None


def _documents_signature(documents: list[Document]) -> str:
    """Create a content signature for cache invalidation."""
    hasher = hashlib.sha256()
    for doc in documents:
        hasher.update(str(doc.id).encode("utf-8"))
        hasher.update((doc.title or "").encode("utf-8"))
        hasher.update((doc.category or "").encode("utf-8"))
        hasher.update((doc.source or "").encode("utf-8"))
        hasher.update((doc.content or "").encode("utf-8"))
    return hasher.hexdigest()


def _tfidf_scores(cleaned_input: str, index: DocumentIndex) -> list[float]:
    """Compute TF-IDF cosine scores against the cached document matrix."""
    if not cleaned_input or index.tfidf_matrix is None:
        return [0.0 for _ in index.documents]

    try:
        input_vector = index.vectorizer.transform([cleaned_input])
    except ValueError as e:
        logger.error(f"[SIMILARITY] TF-IDF transform failed: {e}")
        return [0.0 for _ in index.documents]

    return [
        float(score)
        for score in cosine_similarity(input_vector, index.tfidf_matrix).flatten()
    ]


def _weighted_score(
    tfidf_score: float,
    fuzzy_score: float,
    phrase_overlap_score: float,
) -> float:
    """Combine component scores and keep the result inside 0.0 to 1.0."""
    score = (
        settings.TFIDF_WEIGHT * tfidf_score
        + settings.FUZZY_WEIGHT * fuzzy_score
        + settings.PHRASE_WEIGHT * phrase_overlap_score
    )
    return max(0.0, min(score, 1.0))


def _ngrams(cleaned_text: str, n: int) -> set[str]:
    """Return word n-grams from cleaned text."""
    words = cleaned_text.split()
    if len(words) < n:
        return set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def _phrase_overlap_score(
    input_phrase_sets: dict[int, set[str]],
    doc_phrase_sets: dict[int, set[str]],
) -> float:
    """Measure how much of the submitted text appears as shared phrases."""
    weighted_matches = 0.0
    weighted_total = 0.0

    for n, input_phrases in input_phrase_sets.items():
        if not input_phrases:
            continue
        weight = float(n - 2)
        weighted_total += weight * len(input_phrases)
        weighted_matches += weight * len(input_phrases & doc_phrase_sets.get(n, set()))

    if not weighted_total:
        return 0.0

    return weighted_matches / weighted_total


def _matched_phrases(
    input_phrase_sets: dict[int, set[str]],
    doc_phrase_sets: dict[int, set[str]],
) -> list[str]:
    """Return the strongest shared phrases for reviewer evidence."""
    phrases: list[str] = []
    for n in range(6, 2, -1):
        shared = input_phrase_sets.get(n, set()) & doc_phrase_sets.get(n, set())
        phrases.extend(sorted(shared))
        if len(phrases) >= settings.MAX_MATCHED_PHRASES:
            break

    return phrases[:settings.MAX_MATCHED_PHRASES]


def _chunk_text(text: str) -> list[str]:
    """Split text into small sentence groups for partial-plagiarism evidence."""
    if not text:
        return []

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]

    if not sentences:
        return []

    chunk_size = max(settings.CHUNK_SENTENCE_COUNT, 1)
    return [
        " ".join(sentences[i:i + chunk_size])
        for i in range(0, len(sentences), chunk_size)
    ]


def _suspicious_chunks(
    input_chunks: list[str],
    document_chunks: list[str],
) -> list[ChunkMatch]:
    """Find input chunks that closely resemble chunks in one reference document."""
    if not input_chunks or not document_chunks:
        return []

    matches: list[ChunkMatch] = []
    for input_chunk in input_chunks:
        cleaned_input_chunk = clean_text(input_chunk)
        if not cleaned_input_chunk:
            continue

        best_chunk = ""
        best_score = 0.0
        for document_chunk in document_chunks:
            cleaned_doc_chunk = clean_text(document_chunk)
            if not cleaned_doc_chunk:
                continue

            score = fuzz.token_set_ratio(cleaned_input_chunk, cleaned_doc_chunk) / 100
            if score > best_score:
                best_score = score
                best_chunk = document_chunk

        if best_score >= settings.SUSPICIOUS_CHUNK_THRESHOLD:
            matches.append(
                ChunkMatch(
                    input_chunk=input_chunk,
                    matched_chunk=best_chunk,
                    score=best_score,
                )
            )

    matches.sort(key=lambda chunk: chunk.score, reverse=True)
    return matches[:settings.MAX_SUSPICIOUS_CHUNKS]
