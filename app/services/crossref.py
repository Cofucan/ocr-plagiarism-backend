"""
Crossref API client for fetching academic metadata (official free API).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.services.nlp import extract_keywords, clean_text
from app.services.similarity import calculate_ngram_similarity

logger = logging.getLogger(__name__)

# Simple in-memory cache for educational purposes
# Key: query string, Value: (timestamp, results)
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL: int = 3600  # 1 hour in seconds


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _truncate(text: str | None, max_len: int) -> str | None:
    if not text:
        return None
    text = _normalize_whitespace(text)
    if len(text) <= max_len:
        return text
    return f"{text[:max_len].rstrip()}..."


def _extract_year(item: dict[str, Any]) -> int | None:
    issued = item.get("issued") or {}
    date_parts = issued.get("date-parts") or []
    if not date_parts:
        return None
    first = date_parts[0]
    if not first:
        return None
    year = first[0]
    return int(year) if isinstance(year, int) else None


def _extract_title(item: dict[str, Any]) -> str | None:
    title = item.get("title") or []
    if isinstance(title, list) and title:
        return title[0]
    if isinstance(title, str):
        return title
    return None


def _extract_authors(item: dict[str, Any]) -> list[str]:
    authors = []
    for author in item.get("author", []) or []:
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = " ".join(part for part in [given, family] if part)
        if name:
            authors.append(name)
    return authors


def _normalize_scores(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = [r.get("score") for r in results if isinstance(r.get("score"), (int, float))]
    if not scores:
        return results
    max_score = max(scores)
    if max_score <= 0:
        return results
    for result in results:
        score = result.get("score")
        if isinstance(score, (int, float)):
            result["score"] = round(score / max_score, 4)
    return results


async def fetch_crossref_matches(text: str) -> tuple[list[str], list[dict[str, Any]], float]:
    """
    Query Crossref works endpoint using keyword-based bibliographic search.
    Also calculates plagiarism scores against paper abstracts.

    Returns:
        (keywords, results_with_plagiarism_scores, latency_seconds)
    """
    start_time = time.time()

    keywords = extract_keywords(text)
    if not keywords:
        return [], [], 0.0

    query = " ".join(keywords)
    cleaned_input = clean_text(text)

    # Check cache first
    now = time.time()
    if query in _CACHE:
        cached_time, cached_results = _CACHE[query]
        if now - cached_time < _CACHE_TTL:
            latency = time.time() - start_time
            logger.info("[CROSSREF] Cache hit for query (age: %.1fs)", now - cached_time)
            return keywords, cached_results, latency

    params = {
        "query.bibliographic": query,
        "rows": settings.CROSSREF_MAX_RESULTS,
        "mailto": settings.CROSSREF_MAILTO,
        "select": "DOI,title,author,issued,abstract,URL,publisher,score",
    }

    logger.info("[CROSSREF] Querying Crossref with keywords: %s", keywords)

    async with httpx.AsyncClient(
        base_url=settings.CROSSREF_BASE_URL,
        timeout=settings.CROSSREF_TIMEOUT,
    ) as client:
        response = await client.get("/works", params=params)
        response.raise_for_status()
        payload = response.json()

    items = (payload.get("message") or {}).get("items") or []
    results: list[dict[str, Any]] = []

    for item in items:
        abstract = item.get("abstract")
        abstract_snippet = None
        plagiarism_score = None

        if abstract:
            abstract_snippet = _truncate(_strip_tags(abstract), settings.CROSSREF_SNIPPET_LEN)
            # Calculate plagiarism score against the abstract
            cleaned_abstract = clean_text(abstract_snippet or "")
            if cleaned_abstract and cleaned_input:
                plagiarism_score = calculate_ngram_similarity(cleaned_input, cleaned_abstract)

        results.append(
            {
                "source": "Crossref",
                "doi": item.get("DOI"),
                "title": _extract_title(item),
                "authors": _extract_authors(item),
                "year": _extract_year(item),
                "abstract_snippet": abstract_snippet,
                "score": item.get("score"),
                "url": item.get("URL"),
                "publisher": item.get("publisher"),
                "plagiarism_score": plagiarism_score,
            }
        )

    results = _normalize_scores(results)

    # Cache results for future requests
    _CACHE[query] = (time.time(), results)

    latency = time.time() - start_time
    logger.info("[CROSSREF] Query completed in %.3f seconds", latency)

    return keywords, results, latency
