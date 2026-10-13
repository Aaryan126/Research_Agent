"""Elasticsearch corpus tools supplied to the Google ADK agents."""

import os

from elasticsearch import Elasticsearch


def _client() -> Elasticsearch:
    api_key = os.getenv("ELASTIC_API_KEY", "")
    endpoint = os.getenv("ELASTIC_ENDPOINT", "")
    cloud_id = os.getenv("ELASTIC_CLOUD_ID", "")
    if not api_key or api_key.startswith("your-"):
        raise RuntimeError("Set ELASTIC_API_KEY in .env")
    if endpoint and not endpoint.startswith("https://your-"):
        return Elasticsearch(endpoint, api_key=api_key)
    if cloud_id and not cloud_id.startswith("your-"):
        return Elasticsearch(cloud_id=cloud_id, api_key=api_key)
    raise RuntimeError("Set ELASTIC_ENDPOINT or ELASTIC_CLOUD_ID in .env")


def _hits(response: dict) -> list[dict]:
    return [{"score": hit.get("_score"), **hit["_source"]}
            for hit in response["hits"]["hits"]]


def search_papers(query: str, limit: int = 8) -> dict:
    """Search full text paper passages for evidence about a topic or claim.

    Args:
        query: Search terms describing the evidence to find.
        limit: Maximum passages to return, from 1 to 15.
    """
    response = _client().search(
        index="papers_chunks",
        query={"match": {"chunk_text": query}},
        size=max(1, min(limit, 15)),
        source_includes=["chunk_id", "paper_id", "section_type", "chunk_text"],
    )
    return {"passages": _hits(response)}


def search_metadata(query: str, limit: int = 10) -> dict:
    """Find papers by title, abstract, keywords, author, or paper ID.

    Args:
        query: Topic, title, author, or paper ID to search.
        limit: Maximum papers to return, from 1 to 20.
    """
    response = _client().search(
        index="papers_metadata",
        query={"multi_match": {
            "query": query,
            "fields": ["title^3", "abstract", "tldr", "keywords^2", "authors", "paper_id"],
        }},
        size=max(1, min(limit, 20)),
        source_includes=["paper_id", "title", "authors", "year", "abstract", "citation_count", "doi", "url"],
    )
    return {"papers": _hits(response)}


def get_paper_metadata(paper_ids: list[str]) -> dict:
    """Verify cited paper IDs and retrieve authoritative title, authors and year.

    Args:
        paper_ids: Exact paper IDs from the report references, maximum 30.
    """
    ids = list(dict.fromkeys(paper_ids))[:30]
    if not ids:
        return {"papers": [], "missing_ids": []}
    response = _client().search(
        index="papers_metadata",
        query={"terms": {"paper_id": ids}},
        size=len(ids),
        source_includes=["paper_id", "title", "authors", "year", "citation_count", "doi", "url"],
    )
    papers = _hits(response)
    found = {paper["paper_id"] for paper in papers}
    return {"papers": papers, "missing_ids": [pid for pid in ids if pid not in found]}


def top_cited_papers(query: str, limit: int = 10) -> dict:
    """Find influential papers relevant to a topic, ordered by citation count.

    Args:
        query: Topic to match against paper titles and abstracts.
        limit: Maximum papers to return, from 1 to 20.
    """
    response = _client().search(
        index="papers_metadata",
        query={"multi_match": {"query": query, "fields": ["title^3", "abstract", "keywords^2"]}},
        sort=[{"citation_count": {"order": "desc", "missing": "_last"}}],
        size=max(1, min(limit, 20)),
        source_includes=["paper_id", "title", "authors", "year", "citation_count", "abstract"],
    )
    return {"papers": _hits(response)}


def corpus_overview() -> dict:
    """Count indexed papers and passages and show the paper publication year range."""
    es = _client()
    stats = es.search(
        index="papers_metadata",
        size=0,
        track_total_hits=True,
        aggs={"first_year": {"min": {"field": "year"}},
              "last_year": {"max": {"field": "year"}}},
    )
    return {
        "papers": stats["hits"]["total"]["value"],
        "passages": es.count(index="papers_chunks")["count"],
        "first_year": stats["aggregations"]["first_year"]["value"],
        "last_year": stats["aggregations"]["last_year"]["value"],
    }


def publication_trends(query: str) -> dict:
    """Count matching papers by publication year for a research topic.

    Args:
        query: Topic to match against title and abstract.
    """
    response = _client().search(
        index="papers_metadata",
        query={"multi_match": {"query": query, "fields": ["title^3", "abstract", "keywords^2"]}},
        size=0,
        track_total_hits=True,
        aggs={"years": {"terms": {"field": "year", "size": 100, "order": {"_key": "asc"}}}},
    )
    return {"total": response["hits"]["total"]["value"],
            "years": [{"year": row["key"], "papers": row["doc_count"]}
                      for row in response["aggregations"]["years"]["buckets"]]}
