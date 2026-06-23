"""
Pydantic schemas for the plagiarism analysis API.
Defines request and response models.
"""

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """
    Request schema for the /api/analyze endpoint.

    Attributes:
        student_id: Unique identifier for the student (for logging/tracking)
        text: The raw text extracted from the document image via OCR
    """

    student_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Student ID for tracking purposes",
        examples=["STU-2026-001"],
    )
    text: str = Field(
        ...,
        min_length=10,
        description="The raw text content extracted from the image via OCR",
        examples=["The mitochondria is the powerhouse of the cell..."],
    )


class MatchResult(BaseModel):
    """
    Schema for a single document match result.

    Attributes:
        document_id: Database ID of the matched document
        title: Title of the matched document
        category: Subject category of the document
        source: Origin of the document (e.g., Wikipedia, Thesis)
        score: Cosine similarity score (0.0 to 1.0)
    """

    document_id: int
    title: str
    category: str
    source: str | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    tfidf_score: float = Field(0.0, ge=0.0, le=1.0)
    fuzzy_score: float = Field(0.0, ge=0.0, le=1.0)
    phrase_overlap_score: float = Field(0.0, ge=0.0, le=1.0)
    raw_tfidf_score: float = Field(0.0, ge=0.0, le=1.0)
    corrected_tfidf_score: float = Field(0.0, ge=0.0, le=1.0)
    matched_phrases: list[str] = Field(default_factory=list)
    suspicious_chunks: list["ChunkMatch"] = Field(default_factory=list)


class ChunkMatch(BaseModel):
    """
    Evidence for one suspicious chunk in the submitted text.

    Attributes:
        input_chunk: Submitted text chunk
        matched_chunk: Most similar reference chunk
        score: Chunk-level fuzzy similarity score
    """

    input_chunk: str
    matched_chunk: str
    score: float = Field(..., ge=0.0, le=1.0)


class TextCorrection(BaseModel):
    """
    OCR-style correction applied before similarity scoring.
    """

    original: str
    corrected: str
    confidence: float = Field(..., ge=0.0, le=100.0)


class AnalysisStats(BaseModel):
    """
    Extra metadata that explains how the analysis was performed.
    """

    raw_word_count: int = Field(..., ge=0)
    cleaned_word_count: int = Field(..., ge=0)
    corrected_word_count: int = Field(..., ge=0)
    documents_checked: int = Field(..., ge=0)
    corrections_made: int = Field(..., ge=0)
    corrections: list[TextCorrection] = Field(default_factory=list)
    matched_chunk_count: int = Field(..., ge=0)
    confidence_level: str
    analysis_method: str
    thresholds: dict[str, float]
    score_weights: dict[str, float]


class AnalysisResponse(BaseModel):
    """
    Response schema for the /api/analyze endpoint.

    Attributes:
        student_id: Echo back the student ID from the request
        decision: The plagiarism verdict (High/Moderate/Original)
        decision_color: UI color code (red/yellow/green)
        highest_score: The highest similarity score found
        word_count: Number of words in the cleaned input
        top_matches: List of top N most similar documents
    """

    student_id: str
    decision: str
    decision_color: str = Field(
        ...,
        description="Color code for UI display: red, yellow, or green",
    )
    highest_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Highest similarity score (0.0 = no match, 1.0 = exact copy)",
    )
    word_count: int = Field(..., ge=0, description="Word count of cleaned text")
    top_matches: list[MatchResult] = Field(
        default_factory=list,
        description="Top N most similar documents",
    )
    stats: AnalysisStats


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "healthy"
    app_name: str
    version: str
    database_connected: bool
