"""
Tests for the Crossref external analysis client.
"""

import pytest

pytest.importorskip("httpx")

from app.services import crossref


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, path, params):
        self.calls.append((path, params))
        return FakeResponse(
            {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/example",
                            "title": ["Machine learning in healthcare diagnostics"],
                            "author": [
                                {"given": "Ada", "family": "Lovelace"},
                            ],
                            "issued": {"date-parts": [[2024]]},
                            "abstract": (
                                "<jats:p>Machine learning algorithms in healthcare "
                                "diagnostics support early disease detection using "
                                "patient data.</jats:p>"
                            ),
                            "URL": "https://doi.org/10.1000/example",
                            "publisher": "Example Publisher",
                            "score": 12.0,
                        }
                    ]
                }
            }
        )


@pytest.mark.asyncio
async def test_fetch_crossref_matches_scores_sources_without_network(monkeypatch):
    crossref._CACHE.clear()
    monkeypatch.setattr(crossref.httpx, "AsyncClient", FakeAsyncClient)

    result = await crossref.fetch_crossref_matches(
        (
            "Machine learning algorithms in healthcare diagnostics support "
            "early disease detection using patient data."
        )
    )

    assert result.cache_hit is False
    assert result.query
    assert "query.bibliographic" in result.query_strategies
    assert "query.title" in result.query_strategies
    assert len(result.results) == 1

    source = result.results[0]
    assert source["crossref_relevance_score"] == 1.0
    assert source["text_similarity_score"] > 0
    assert source["external_risk_score"] > 0
    assert source["matched_phrases"]
    assert source["source_quality"]["has_doi"] is True
    assert source["source_quality"]["has_abstract"] is True
    assert source["source_quality"]["metadata_completeness"] == 1.0

    cached_result = await crossref.fetch_crossref_matches(
        (
            "Machine learning algorithms in healthcare diagnostics support "
            "early disease detection using patient data."
        )
    )
    assert cached_result.cache_hit is True
