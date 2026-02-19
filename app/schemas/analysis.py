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


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "healthy"
    app_name: str
    version: str
    database_connected: bool


class ExternalSourceResult(BaseModel):
    """
    Schema for a single external source result (Crossref).
    """

    source: str = "Crossref"
    doi: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract_snippet: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    url: str | None = None
    publisher: str | None = None
    plagiarism_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="N-gram plagiarism score (0=no match, 1=plagiarism). Higher indicates more plagiarism.",
    )


class ExternalAnalysisResponse(BaseModel):
    """
    Response schema for the /api/analyze/external endpoint.
    """

    student_id: str
    query_keywords: list[str] = Field(default_factory=list)
    result_count: int = Field(..., ge=0)
    sources: list[ExternalSourceResult] = Field(default_factory=list)
    latency_seconds: float = Field(
        ...,
        ge=0.0,
        description="Time taken to fetch external results (for educational reporting)",
    )
