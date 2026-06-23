"""
Crossref API client for fetching academic metadata (official free API).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from rapidfuzz import fuzz

from app.config import settings
from app.services.nlp import extract_keywords, clean_text
from app.services.similarity import calculate_ngram_similarity

logger = logging.getLogger(__name__)

# Simple in-memory cache for educational purposes
# Key: normalized query string, Value: cached fetch result fields
_CACHE: dict[str, tuple[float, list[str], str, list[str], list[dict[str, Any]]]] = {}
_CACHE_TTL: int = 3600  # 1 hour in seconds

GENERIC_ACADEMIC_TERMS = {
    "analysis",
    "article",
    "based",
    "case",
    "data",
    "development",
    "effect",
    "findings",
    "method",
    "methods",
    "paper",
    "research",
    "result",
    "results",
    "review",
    "study",
    "system",
    "using",
}


@dataclass
class CrossrefFetchResult:
    """Structured result from a Crossref analysis request."""

    keywords: list[str]
    query: str
    query_strategies: list[str]
    results: list[dict[str, Any]]
    latency_seconds: float
    cache_hit: bool = False


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


def _cache_key(query: str) -> str:
    return f"{_normalize_whitespace(query).lower()}|rows={settings.CROSSREF_MAX_RESULTS}"


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


def _extract_keyphrases(text: str, max_phrases: int = 4) -> list[str]:
    """Extract simple 2- and 3-word phrases for more specific Crossref queries."""
    cleaned = clean_text(text)
    tokens = [
        token
        for token in cleaned.split()
        if token not in GENERIC_ACADEMIC_TERMS
        and len(token) >= settings.CROSSREF_MIN_TOKEN_LEN
    ]
    phrases: list[str] = []

    for size in (3, 2):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            phrase = " ".join(tokens[index:index + size])
            if phrase not in phrases:
                phrases.append(phrase)
            if len(phrases) >= max_phrases:
                return phrases

    return phrases


def _build_query(text: str, keywords: list[str]) -> tuple[str, list[str]]:
    """Build a transparent Crossref query from keywords plus stronger phrases."""
    filtered_keywords = [
        keyword
        for keyword in keywords
        if keyword not in GENERIC_ACADEMIC_TERMS
    ]
    keyphrases = _extract_keyphrases(text)
    query_parts = keyphrases[:2] + filtered_keywords[:6]
    query = " ".join(dict.fromkeys(query_parts))
    return query or " ".join(keywords), keyphrases


def _normalize_scores(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = [
        r.get("crossref_raw_score")
        for r in results
        if isinstance(r.get("crossref_raw_score"), (int, float))
    ]
    if not scores:
        return results
    max_score = max(scores)
    if max_score <= 0:
        return results
    for result in results:
        score = result.get("crossref_raw_score")
        if isinstance(score, (int, float)):
            normalized = round(score / max_score, 4)
            result["crossref_relevance_score"] = normalized
            result["score"] = normalized
    return results


def _source_quality(item: dict[str, Any], abstract: str | None) -> dict[str, Any]:
    """Summarize how much usable metadata Crossref returned for one work."""
    checks = {
        "has_doi": bool(item.get("DOI")),
        "has_title": bool(_extract_title(item)),
        "has_authors": bool(item.get("author")),
        "has_year": _extract_year(item) is not None,
        "has_abstract": bool(abstract),
        "has_url": bool(item.get("URL")),
        "has_publisher": bool(item.get("publisher")),
    }
    completeness = sum(checks.values()) / len(checks)
    return {
        **checks,
        "metadata_completeness": round(completeness, 4),
    }


def _matched_phrases(cleaned_input: str, cleaned_candidate: str) -> list[str]:
    """Return shared phrase evidence from cleaned submitted text and source text."""
    phrases: list[str] = []
    input_tokens = cleaned_input.split()
    candidate_tokens = cleaned_candidate.split()

    for size in range(6, 2, -1):
        if len(input_tokens) < size or len(candidate_tokens) < size:
            continue

        input_phrases = {
            " ".join(input_tokens[index:index + size])
            for index in range(len(input_tokens) - size + 1)
        }
        candidate_phrases = {
            " ".join(candidate_tokens[index:index + size])
            for index in range(len(candidate_tokens) - size + 1)
        }

        for phrase in sorted(input_phrases & candidate_phrases):
            if phrase not in phrases:
                phrases.append(phrase)
            if len(phrases) >= settings.MAX_MATCHED_PHRASES:
                return phrases

    return phrases


def _text_similarity(cleaned_input: str, cleaned_candidate: str) -> float | None:
    """Combine n-gram overlap and fuzzy similarity for Crossref metadata text."""
    if not cleaned_input or not cleaned_candidate:
        return None

    ngram_score = calculate_ngram_similarity(cleaned_input, cleaned_candidate)
    fuzzy_score = fuzz.token_set_ratio(cleaned_input, cleaned_candidate) / 100
    return round((0.65 * ngram_score) + (0.35 * fuzzy_score), 4)


def _external_risk_score(result: dict[str, Any]) -> float:
    """Combine source relevance, text similarity, and metadata quality."""
    text_similarity = result.get("text_similarity_score") or 0.0
    relevance = result.get("crossref_relevance_score") or 0.0
    quality = (result.get("source_quality") or {}).get("metadata_completeness") or 0.0
    return round((0.60 * text_similarity) + (0.25 * relevance) + (0.15 * quality), 4)


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate Crossref works by DOI, falling back to normalized title."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in items:
        title = _extract_title(item) or ""
        key = (item.get("DOI") or _normalize_whitespace(title).lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


async def fetch_crossref_matches(text: str) -> CrossrefFetchResult:
    """
    Query Crossref works endpoint using keyword-based bibliographic search.
    Also calculates external similarity/risk scores against returned metadata.

    Returns:
        CrossrefFetchResult with query, cache, source, and latency metadata.
    """
    start_time = time.time()

    keywords = extract_keywords(text)
    if not keywords:
        return CrossrefFetchResult([], "", [], [], 0.0)

    query, keyphrases = _build_query(text, keywords)
    cleaned_input = clean_text(text)
    query_strategies = ["query.bibliographic"]
    if keyphrases:
        query_strategies.append("query.title")

    # Check cache first
    now = time.time()
    cache_key = _cache_key(query)
    if cache_key in _CACHE:
        cached_time, cached_keywords, cached_query, cached_strategies, cached_results = _CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            latency = time.time() - start_time
            logger.info("[CROSSREF] Cache hit for query (age: %.1fs)", now - cached_time)
            return CrossrefFetchResult(
                keywords=cached_keywords,
                query=cached_query,
                query_strategies=cached_strategies,
                results=cached_results,
                latency_seconds=latency,
                cache_hit=True,
            )

    logger.info("[CROSSREF] Querying Crossref with keywords: %s", keywords)

    async with httpx.AsyncClient(
        base_url=settings.CROSSREF_BASE_URL,
        timeout=settings.CROSSREF_TIMEOUT,
    ) as client:
        payloads = []
        base_params = {
            "rows": settings.CROSSREF_MAX_RESULTS,
            "mailto": settings.CROSSREF_MAILTO,
            "select": "DOI,title,author,issued,abstract,URL,publisher,score",
        }

        bibliographic_response = await client.get(
            "/works",
            params={**base_params, "query.bibliographic": query},
        )
        bibliographic_response.raise_for_status()
        payloads.append(bibliographic_response.json())

        if keyphrases:
            title_response = await client.get(
                "/works",
                params={**base_params, "query.title": keyphrases[0]},
            )
            title_response.raise_for_status()
            payloads.append(title_response.json())

    items = []
    for payload in payloads:
        items.extend((payload.get("message") or {}).get("items") or [])
    items = _dedupe_items(items)[:settings.CROSSREF_MAX_RESULTS]
    results: list[dict[str, Any]] = []

    for item in items:
        abstract = item.get("abstract")
        stripped_abstract = _strip_tags(abstract) if abstract else None
        abstract_snippet = _truncate(stripped_abstract, settings.CROSSREF_SNIPPET_LEN)
        title = _extract_title(item)
        quality = _source_quality(item, abstract)
        candidate_text = " ".join(
            part
            for part in [title or "", stripped_abstract or ""]
            if part
        )
        cleaned_candidate = clean_text(candidate_text)
        text_similarity_score = _text_similarity(cleaned_input, cleaned_candidate)
        matched_phrases = _matched_phrases(cleaned_input, cleaned_candidate)

        result = {
            "source": "Crossref",
            "doi": item.get("DOI"),
            "title": title,
            "authors": _extract_authors(item),
            "year": _extract_year(item),
            "abstract_snippet": abstract_snippet,
            "score": item.get("score"),
            "crossref_raw_score": item.get("score"),
            "crossref_relevance_score": None,
            "url": item.get("URL"),
            "publisher": item.get("publisher"),
            "plagiarism_score": text_similarity_score,
            "text_similarity_score": text_similarity_score,
            "external_risk_score": 0.0,
            "matched_phrases": matched_phrases,
            "source_quality": quality,
            "similarity_basis": "title_and_abstract" if abstract_snippet else "title_only",
        }
        results.append(result)

    results = _normalize_scores(results)
    for result in results:
        result["external_risk_score"] = _external_risk_score(result)

    results.sort(
        key=lambda result: (
            result.get("external_risk_score") or 0.0,
            result.get("crossref_relevance_score") or 0.0,
        ),
        reverse=True,
    )

    # Cache results for future requests
    _CACHE[cache_key] = (
        time.time(),
        keywords,
        query,
        query_strategies,
        results,
    )

    latency = time.time() - start_time
    logger.info("[CROSSREF] Query completed in %.3f seconds", latency)

    return CrossrefFetchResult(
        keywords=keywords,
        query=query,
        query_strategies=query_strategies,
        results=results,
        latency_seconds=latency,
        cache_hit=False,
    )
