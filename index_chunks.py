"""Index parsed text chunks into the papers_chunks Elasticsearch index."""

import json
import os
import sys

from elasticsearch import helpers
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import EMBEDDING_MODEL, get_es_client

CHUNKS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "parsed_chunks.json"
)


def main():
    """Load parsed chunks, generate embeddings, and bulk index into ES."""
    print("=" * 60)
    print("INDEX CHUNKS")
    print("=" * 60)

    # Connect to ES early
    try:
        es = get_es_client()
        if not es.ping():
            print("Error: Cannot connect to Elasticsearch")
            sys.exit(1)
        print("Connected to Elasticsearch")
    except Exception as e:
        print(f"Error: Elasticsearch connection failed: {e}")
        sys.exit(1)

    if not os.path.exists(CHUNKS_PATH):
        print(f"Error: {CHUNKS_PATH} not found. Run parse_pdfs.py first.")
        sys.exit(1)

    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks from parsed_chunks.json")

    if not chunks:
        print("Warning: No chunks to index")
        return {"chunks_indexed": 0, "errors": 0, "total_in_index": 0}

    # Generate embeddings
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [c["chunk_text"] for c in chunks]
    print("Generating chunk embeddings...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    for i, chunk in enumerate(chunks):
        chunk["chunk_embedding"] = embeddings[i].tolist()

    # Bulk index
    def generate_actions():
        for chunk in chunks:
            yield {
                "_index": "papers_chunks",
                "_id": chunk["chunk_id"],
                "_source": chunk,
            }

    print("Indexing into papers_chunks...")
    success, errors = helpers.bulk(
        es,
        generate_actions(),
        chunk_size=500,
        raise_on_error=False,
        raise_on_exception=False,
    )

    error_count = len(errors) if isinstance(errors, list) else 0
    if error_count > 0:
        print(f"Warning: {error_count} indexing errors")
        for err in errors[:5]:
            print(f"  {err}")

    es.indices.refresh(index="papers_chunks")
    count = es.count(index="papers_chunks")["count"]
    print(f"Indexed {success} chunks ({count} total in index)")

    summary = {
        "chunks_indexed": success,
        "errors": error_count,
        "total_in_index": count,
    }
    return summary


if __name__ == "__main__":
    main()
