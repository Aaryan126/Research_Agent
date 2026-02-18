"""Create (or recreate) the papers_metadata and papers_chunks Elasticsearch indexes."""

from config import get_es_client

INDEXES = {
    "papers_metadata": {
        "mappings": {
            "properties": {
                "paper_id":            {"type": "keyword"},
                "title":               {"type": "text"},
                "authors":             {"type": "keyword"},
                "year":                {"type": "integer"},
                "publication_date":    {"type": "date"},
                "abstract":            {"type": "text"},
                "abstract_embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine",
                },
                "tldr":                {"type": "text"},
                "citation_count":      {"type": "integer"},
                "reference_count":     {"type": "integer"},
                "influential_citation_count": {"type": "integer"},
                "fields_of_study":     {"type": "keyword"},
                "publication_types":   {"type": "keyword"},
                "keywords":            {"type": "keyword"},
                "source_venue":        {"type": "keyword"},
                "doi":                 {"type": "keyword"},
                "arxiv_id":            {"type": "keyword"},
                "url":                 {"type": "keyword"},
                "semantic_scholar_url": {"type": "keyword"},
            }
        }
    },
    "papers_chunks": {
        "mappings": {
            "properties": {
                "chunk_id":        {"type": "keyword"},
                "paper_id":        {"type": "keyword"},
                "chunk_text":      {"type": "text"},
                "chunk_embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine",
                },
                "section_type":    {"type": "keyword"},
                "chunk_index":     {"type": "integer"},
            }
        }
    },
}


def create_indexes():
    try:
        es = get_es_client()
    except Exception as e:
        print(f"Failed to connect to Elasticsearch: {e}")
        return

    for name, body in INDEXES.items():
        try:
            if es.indices.exists(index=name):
                es.indices.delete(index=name)
                print(f"Deleted existing index: {name}")

            es.indices.create(index=name, body=body)
            print(f"Created index: {name}")
        except Exception as e:
            print(f"Error with index '{name}': {e}")


if __name__ == "__main__":
    create_indexes()
