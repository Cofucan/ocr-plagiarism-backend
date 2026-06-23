from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Document
from app.services.similarity import (
    analyze_similarity,
    clear_document_index_cache,
    get_decision,
)


def _session_with_documents(documents):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()

    for document in documents:
        db.add(Document(**document))
    db.commit()
    clear_document_index_cache()
    return db


def test_analysis_returns_component_scores_and_evidence():
    db = _session_with_documents(
        [
            {
                "title": "Cell Energy",
                "category": "Biology",
                "source": "Fixture",
                "content": (
                    "Mitochondria generate most of the cell supply of adenosine "
                    "triphosphate. ATP is used as a source of chemical energy."
                ),
            },
            {
                "title": "Circuits",
                "category": "Engineering",
                "source": "Fixture",
                "content": "Ohm law describes voltage current and resistance in circuits.",
            },
        ]
    )

    try:
        analysis = analyze_similarity(
            (
                "Mitochondria generate most of the cell supply of adenosine "
                "triphosphate. ATP is used as a source of chemical energy."
            ),
            db,
        )
    finally:
        db.close()

    top_match = analysis.matches[0]
    assert top_match.title == "Cell Energy"
    assert top_match.similarity_score > 0.8
    assert top_match.tfidf_score > 0.8
    assert top_match.fuzzy_score > 0.8
    assert top_match.phrase_overlap_score > 0.8
    assert top_match.matched_phrases
    assert top_match.suspicious_chunks
    assert analysis.metadata.documents_checked == 2
    assert analysis.metadata.score_weights["tfidf"] > 0


def test_unrelated_text_has_no_significant_match():
    db = _session_with_documents(
        [
            {
                "title": "Thermodynamics",
                "category": "Physics",
                "source": "Fixture",
                "content": "Energy entropy temperature and heat define thermal systems.",
            }
        ]
    )

    try:
        analysis = analyze_similarity(
            (
                "Poetry can use imagery rhythm metaphor and narrative voice "
                "to communicate emotion."
            ),
            db,
        )
    finally:
        db.close()

    assert analysis.matches[0].similarity_score < 0.4
    assert get_decision(analysis.matches[0].similarity_score) == "No Significant Match Found"
