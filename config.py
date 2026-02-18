import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

ELASTIC_CLOUD_ID = os.getenv("ELASTIC_CLOUD_ID")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
ELASTIC_ENDPOINT = os.getenv("ELASTIC_ENDPOINT")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
PAPERS_PDF_DIR = os.getenv("PAPERS_PDF_DIR")


def get_es_client():
    """Create and return an Elasticsearch client."""
    if ELASTIC_ENDPOINT and ELASTIC_ENDPOINT != "your_endpoint_url_here":
        return Elasticsearch(
            ELASTIC_ENDPOINT,
            api_key=ELASTIC_API_KEY,
        )
    if ELASTIC_CLOUD_ID and ELASTIC_CLOUD_ID != "your_cloud_id_here":
        return Elasticsearch(
            cloud_id=ELASTIC_CLOUD_ID,
            api_key=ELASTIC_API_KEY,
        )
    print("Error: Set ELASTIC_ENDPOINT or ELASTIC_CLOUD_ID in .env")
    sys.exit(1)


def test_connection():
    """Ping Elasticsearch and print cluster info."""
    try:
        es = get_es_client()
        if es.ping():
            info = es.info()
            print(f"Connected to Elasticsearch cluster: {info['cluster_name']}")
            print(f"Version: {info['version']['number']}")
            return True
        else:
            print("Elasticsearch ping failed.")
            return False
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
