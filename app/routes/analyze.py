"""
API routes for plagiarism analysis.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    ExternalAnalysisResponse,
    ExternalSourceResult,
    AnalysisStats,
    ChunkMatch,
    MatchResult,
    TextCorrection,
)
from app.services.crossref import fetch_crossref_matches
from app.services.nlp import clean_text
from app.services.similarity import (
    analyze_similarity,
    get_decision,
    get_decision_color,
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyze text for plagiarism",
    description=(
        "Compares input text against the document repository and returns hybrid "
        "similarity scores, evidence snippets, OCR correction stats, and a verdict."
    ),
)
async def analyze_text(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """
    Analyze submitted text for plagiarism.

    This endpoint:
    1. Cleans and preprocesses the input text
    2. Compares it against all documents using cached TF-IDF, fuzzy, and phrase signals
    3. Returns the top matches with scores and reviewer evidence
    4. Provides a decision based on configurable thresholds

    Args:
        request: AnalysisRequest containing student_id and text
        db: Database session (injected)

    Returns:
        AnalysisResponse with decision, scores, and matched documents
    """
    # === LOGGING: Incoming Request ===
    logger.info("=" * 60)
    logger.info("[ANALYZE] New request received")
    logger.info(f"[ANALYZE] Student ID: {request.student_id}")
    logger.info(f"[ANALYZE] Raw text length: {len(request.text)} chars")
    logger.info(f"[ANALYZE] Raw text preview (first 200 chars): {request.text[:200]!r}")
    logger.info(f"[ANALYZE] Raw text preview (last 100 chars): {request.text[-100:]!r}")

    # Validate that text has meaningful content after cleaning
    cleaned_text = clean_text(request.text)
    word_count = len(cleaned_text.split()) if cleaned_text else 0

    # === LOGGING: After Cleaning ===
    logger.info(f"[ANALYZE] Cleaned text length: {len(cleaned_text)} chars")
    logger.info(f"[ANALYZE] Word count after cleaning: {word_count}")
    logger.info(f"[ANALYZE] Cleaned text preview: {cleaned_text[:200]!r}")

    if word_count < 5:
        raise HTTPException(
            status_code=400,
            detail="Text too short for analysis. Please provide at least 5 meaningful words.",
        )

    # Find top matching documents and analysis metadata
    logger.info("[ANALYZE] Calling analyze_similarity...")
    analysis = analyze_similarity(request.text, db)
    matches = analysis.matches
    logger.info(f"[ANALYZE] Found {len(matches)} matches")

    # Determine highest score and decision
    highest_score = matches[0].similarity_score if matches else 0.0
    decision = get_decision(highest_score)
    decision_color = get_decision_color(decision)

    # === LOGGING: Results ===
    logger.info(f"[ANALYZE] Highest score: {highest_score:.4f}")
    logger.info(f"[ANALYZE] Decision: {decision}")
    for i, m in enumerate(matches):
        logger.info(f"[ANALYZE] Match {i+1}: {m.title} (score: {m.similarity_score:.4f})")

    # Convert internal MatchResult to Pydantic schema
    match_results = [
        MatchResult(
            document_id=m.document_id,
            title=m.title,
            category=m.category,
            source=m.source,
            score=round(m.similarity_score, 4),
            tfidf_score=round(m.tfidf_score, 4),
            fuzzy_score=round(m.fuzzy_score, 4),
            phrase_overlap_score=round(m.phrase_overlap_score, 4),
            raw_tfidf_score=round(m.raw_tfidf_score, 4),
            corrected_tfidf_score=round(m.corrected_tfidf_score, 4),
            matched_phrases=m.matched_phrases,
            suspicious_chunks=[
                ChunkMatch(
                    input_chunk=chunk.input_chunk,
                    matched_chunk=chunk.matched_chunk,
                    score=round(chunk.score, 4),
                )
                for chunk in m.suspicious_chunks
            ],
        )
        for m in matches
    ]
    stats = AnalysisStats(
        raw_word_count=analysis.metadata.raw_word_count,
        cleaned_word_count=analysis.metadata.cleaned_word_count,
        corrected_word_count=analysis.metadata.corrected_word_count,
        documents_checked=analysis.metadata.documents_checked,
        corrections_made=analysis.metadata.corrections_made,
        corrections=[
            TextCorrection(
                original=correction.original,
                corrected=correction.corrected,
                confidence=round(correction.confidence, 2),
            )
            for correction in analysis.metadata.corrections
        ],
        matched_chunk_count=analysis.metadata.matched_chunk_count,
        confidence_level=analysis.metadata.confidence_level,
        analysis_method=analysis.metadata.analysis_method,
        thresholds=analysis.metadata.thresholds,
        score_weights=analysis.metadata.score_weights,
    )

    return AnalysisResponse(
        student_id=request.student_id,
        decision=decision,
        decision_color=decision_color,
        highest_score=round(highest_score, 4),
        word_count=word_count,
        top_matches=match_results,
        stats=stats,
    )


@router.post(
    "/analyze/external",
    response_model=ExternalAnalysisResponse,
    summary="Analyze text against Crossref",
    description="Queries Crossref for related academic works and returns metadata with snippets.",
)
async def analyze_external(
    request: AnalysisRequest,
) -> ExternalAnalysisResponse:
    """
    Analyze submitted text against Crossref.

    This endpoint:
    1. Cleans and validates the input text
    2. Extracts keywords
    3. Queries Crossref and returns metadata with abstract snippets
    """
    # === LOGGING: Incoming Request ===
    logger.info("=" * 60)
    logger.info("[ANALYZE-EXTERNAL] New request received")
    logger.info(f"[ANALYZE-EXTERNAL] Student ID: {request.student_id}")
    logger.info(f"[ANALYZE-EXTERNAL] Raw text length: {len(request.text)} chars")

    cleaned_text = clean_text(request.text)
    word_count = len(cleaned_text.split()) if cleaned_text else 0

    logger.info(f"[ANALYZE-EXTERNAL] Word count after cleaning: {word_count}")

    if word_count < 5:
        raise HTTPException(
            status_code=400,
            detail="Text too short for external analysis. Please provide at least 5 meaningful words.",
        )

    try:
        keywords, results, latency = await fetch_crossref_matches(request.text)
    except httpx.HTTPError as exc:
        logger.exception("[ANALYZE-EXTERNAL] Crossref request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Crossref service unavailable. Please try again later.",
        ) from exc

    sources = [ExternalSourceResult(**result) for result in results]

    logger.info(f"[ANALYZE-EXTERNAL] Returned {len(sources)} sources in {latency:.3f}s")

    return ExternalAnalysisResponse(
        student_id=request.student_id,
        query_keywords=keywords,
        result_count=len(sources),
        sources=sources,
        latency_seconds=round(latency, 3),
    )
