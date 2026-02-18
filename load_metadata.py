"""Load paper metadata from JSON into the papers_metadata Elasticsearch index."""

import json
import os
import sys

from elasticsearch import helpers
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import EMBEDDING_MODEL, PAPERS_PDF_DIR, get_es_client

METADATA_JSON = os.path.join(
    PAPERS_PDF_DIR, "AI_Agent_Architectures_and_Frameworks.json"
)


def transform_paper(paper):
    """Transform a raw metadata record into the ES schema."""
    arxiv_id = paper.get("arxivId", "").strip()
    ss_url = paper.get("semanticScholarUrl", "").strip()

    if arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    elif ss_url:
        url = ss_url
    else:
        url = None

    def split_field(value):
        """Split a semicolon-separated string into a list."""
        if not value or not value.strip():
            return []
        return [v.strip() for v in value.split("; ") if v.strip()]

    def empty_to_none(value):
        """Convert empty strings to None for keyword/date fields."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    pub_date = empty_to_none(paper.get("publicationDate", ""))

    return {
        "paper_id": paper["paperId"],
        "title": paper.get("title", ""),
        "authors": split_field(paper.get("authors", "")),
        "year": paper.get("year"),
        "publication_date": pub_date,
        "abstract": paper.get("abstract", ""),
        "tldr": empty_to_none(paper.get("tldr", "")),
        "citation_count": paper.get("citationCount", 0),
        "reference_count": paper.get("referenceCount", 0),
        "influential_citation_count": paper.get("influentialCitationCount", 0),
        "fields_of_study": split_field(paper.get("fieldsOfStudy", "")),
        "publication_types": split_field(paper.get("publicationTypes", "")),
        "keywords": [],
        "source_venue": empty_to_none(paper.get("venue", "")),
        "doi": empty_to_none(paper.get("doi", "")),
        "arxiv_id": empty_to_none(arxiv_id),
        "url": url,
        "semantic_scholar_url": empty_to_none(ss_url),
    }


def main():
    """Load metadata JSON, generate embeddings, and bulk index into ES."""
    print("=" * 60)
    print("LOAD METADATA")
    print("=" * 60)

    # Connect to ES early to fail fast
    try:
        es = get_es_client()
        if not es.ping():
            print("Error: Cannot connect to Elasticsearch")
            sys.exit(1)
        print("Connected to Elasticsearch")
    except Exception as e:
        print(f"Error: Elasticsearch connection failed: {e}")
        sys.exit(1)

    with open(METADATA_JSON, "r", encoding="utf-8") as f:
        raw_papers = json.load(f)
    print(f"Loaded {len(raw_papers)} papers from metadata JSON")

    papers = [transform_paper(p) for p in raw_papers]

    # Generate abstract embeddings
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts_to_encode = []
    for p in papers:
        abstract = p.get("abstract", "").strip()
        if abstract:
            texts_to_encode.append(abstract)
        else:
            # Fallback to title
            texts_to_encode.append(p.get("title", ""))

    print("Generating abstract embeddings...")
    embeddings = model.encode(
        texts_to_encode, batch_size=32, show_progress_bar=True
    )

    for i, paper in enumerate(papers):
        paper["abstract_embedding"] = embeddings[i].tolist()

    # Bulk index
    def generate_actions():
        for paper in papers:
            yield {
                "_index": "papers_metadata",
                "_id": paper["paper_id"],
                "_source": paper,
            }

    print("Indexing into papers_metadata...")
    success, errors = helpers.bulk(
        es, generate_actions(), raise_on_error=False, raise_on_exception=False
    )

    error_count = len(errors) if isinstance(errors, list) else 0
    if error_count > 0:
        print(f"Warning: {error_count} indexing errors")
        for err in errors[:5]:
            print(f"  {err}")

    es.indices.refresh(index="papers_metadata")
    count = es.count(index="papers_metadata")["count"]
    print(f"Indexed {success} papers ({count} total in index)")

    summary = {
        "papers_loaded": success,
        "errors": error_count,
        "total_in_index": count,
    }
    return summary


if __name__ == "__main__":
    main()
