"""
API routes for plagiarism analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, MatchResult
from app.services.nlp import clean_text, get_word_count
from app.services.similarity import (
    find_top_matches,
    get_decision,
    get_decision_color,
)

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyze text for plagiarism",
    description="Compares input text against the document repository and returns similarity scores.",
)
async def analyze_text(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """
    Analyze submitted text for plagiarism.

    This endpoint:
    1. Cleans and preprocesses the input text
    2. Compares it against all documents in the repository using TF-IDF + Cosine Similarity
    3. Returns the top 3 most similar documents with their scores
    4. Provides a decision based on configurable thresholds

    Args:
        request: AnalysisRequest containing student_id and text
        db: Database session (injected)

    Returns:
        AnalysisResponse with decision, scores, and matched documents
    """
    # Validate that text has meaningful content after cleaning
    cleaned_text = clean_text(request.text)
    word_count = len(cleaned_text.split()) if cleaned_text else 0

    if word_count < 5:
        raise HTTPException(
            status_code=400,
            detail="Text too short for analysis. Please provide at least 5 meaningful words.",
        )

    # Find top matching documents
    matches = find_top_matches(request.text, db)

    # Determine highest score and decision
    highest_score = matches[0].similarity_score if matches else 0.0
    decision = get_decision(highest_score)
    decision_color = get_decision_color(decision)

    # Convert internal MatchResult to Pydantic schema
    match_results = [
        MatchResult(
            document_id=m.document_id,
            title=m.title,
            category=m.category,
            source=m.source,
            score=round(m.similarity_score, 4),
        )
        for m in matches
    ]

    return AnalysisResponse(
        student_id=request.student_id,
        decision=decision,
        decision_color=decision_color,
        highest_score=round(highest_score, 4),
        word_count=word_count,
        top_matches=match_results,
    )
