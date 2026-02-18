"""Validate the ingestion pipeline by running keyword, vector, ES|QL, and spot-check queries."""

import sys

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, get_es_client


def keyword_search(es):
    """BM25 keyword search on chunk_text for 'multi-agent'."""
    print("\n" + "-" * 50)
    print("1. KEYWORD SEARCH: 'multi-agent' on papers_chunks")
    print("-" * 50)

    resp = es.search(
        index="papers_chunks",
        body={
            "query": {"match": {"chunk_text": "multi-agent"}},
            "size": 3,
            "_source": ["chunk_id", "paper_id", "section_type", "chunk_text"],
        },
    )

    hits = resp["hits"]["hits"]
    print(f"Total hits: {resp['hits']['total']['value']}")
    for i, hit in enumerate(hits):
        src = hit["_source"]
        snippet = src["chunk_text"][:200].replace("\n", " ")
        print(f"\n  [{i+1}] score={hit['_score']:.2f} | {src['chunk_id']}")
        print(f"      section: {src['section_type']}")
        print(f"      text: {snippet}...")

    return len(hits) > 0


def vector_search(es, model):
    """KNN vector search on chunk_embedding."""
    print("\n" + "-" * 50)
    print("2. VECTOR SEARCH: 'how do AI agents handle errors?'")
    print("-" * 50)

    query_text = "how do AI agents handle errors?"
    query_vec = model.encode(query_text).tolist()

    resp = es.search(
        index="papers_chunks",
        body={
            "knn": {
                "field": "chunk_embedding",
                "query_vector": query_vec,
                "k": 3,
                "num_candidates": 50,
            },
            "_source": ["chunk_id", "paper_id", "section_type", "chunk_text"],
        },
    )

    hits = resp["hits"]["hits"]
    print(f"Total hits: {len(hits)}")
    for i, hit in enumerate(hits):
        src = hit["_source"]
        snippet = src["chunk_text"][:200].replace("\n", " ")
        print(f"\n  [{i+1}] score={hit['_score']:.4f} | {src['chunk_id']}")
        print(f"      section: {src['section_type']}")
        print(f"      text: {snippet}...")

    return len(hits) > 0


def esql_search(es):
    """ES|QL aggregation query on papers_metadata."""
    print("\n" + "-" * 50)
    print("3. ES|QL: Papers per year (>= 2023)")
    print("-" * 50)

    query = (
        "FROM papers_metadata "
        "| WHERE year >= 2023 "
        "| STATS count = COUNT(*) BY year "
        "| SORT year"
    )

    try:
        resp = es.esql.query(query=query, format="json")
        columns = resp.get("columns", [])
        values = resp.get("values", [])

        col_names = [c["name"] for c in columns]
        print(f"  {'  |  '.join(col_names)}")
        print(f"  {'-' * 20}")
        for row in values:
            print(f"  {row[0]:>5}  |  {row[1]}")

        return len(values) > 0
    except Exception as e:
        print(f"  ES|QL query failed: {e}")
        print("  (ES|QL requires Elasticsearch 8.11+)")
        return False


def spot_check(es):
    """Pick one paper and show its chunk count + first chunk."""
    print("\n" + "-" * 50)
    print("4. SPOT CHECK: Random paper chunk details")
    print("-" * 50)

    # Get a paper_id from metadata
    meta_resp = es.search(
        index="papers_metadata",
        body={"query": {"match_all": {}}, "size": 1, "_source": ["paper_id", "title"]},
    )

    if not meta_resp["hits"]["hits"]:
        print("  No papers found in metadata index")
        return False

    paper = meta_resp["hits"]["hits"][0]["_source"]
    paper_id = paper["paper_id"]
    title = paper["title"]

    print(f"  Paper: {title[:80]}")
    print(f"  ID: {paper_id}")

    # Count chunks for this paper
    count_resp = es.count(
        index="papers_chunks",
        body={"query": {"term": {"paper_id": paper_id}}},
    )
    chunk_count = count_resp["count"]
    print(f"  Chunks: {chunk_count}")

    # Get first chunk
    chunk_resp = es.search(
        index="papers_chunks",
        body={
            "query": {"term": {"paper_id": paper_id}},
            "sort": [{"chunk_index": "asc"}],
            "size": 1,
            "_source": ["chunk_id", "section_type", "chunk_text"],
        },
    )

    if chunk_resp["hits"]["hits"]:
        chunk = chunk_resp["hits"]["hits"][0]["_source"]
        snippet = chunk["chunk_text"][:300].replace("\n", " ")
        print(f"  First chunk ({chunk['chunk_id']}, {chunk['section_type']}):")
        print(f"    {snippet}...")

    return chunk_count > 0


def main():
    print("=" * 60)
    print("SEARCH VALIDATION TESTS")
    print("=" * 60)

    try:
        es = get_es_client()
        if not es.ping():
            print("Error: Cannot connect to Elasticsearch")
            sys.exit(1)
        print("Connected to Elasticsearch")
    except Exception as e:
        print(f"Error: Elasticsearch connection failed: {e}")
        sys.exit(1)

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    results = {}
    results["keyword"] = keyword_search(es)
    results["vector"] = vector_search(es, model)
    results["esql"] = esql_search(es)
    results["spot_check"] = spot_check(es)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  {name:<15} {status}")

    if all_passed:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed — check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
