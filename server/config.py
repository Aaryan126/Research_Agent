"""Server configuration — loads environment variables from project root .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

KIBANA_URL = os.getenv("KIBANA_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")

RESEARCHER_AGENT_ID = "research_literature_review_agent"
REVIEWER_AGENT_ID = "peer_review_agent"
CLAIM_VERIFICATION_AGENT_ID = "claim_verification_agent"
MAX_ITERATIONS = 2
AGENT_TIMEOUT = 600

HEADERS = {
    "Content-Type": "application/json",
    "kbn-xsrf": "true",
    "x-elastic-internal-origin": "Kibana",
    "Authorization": f"ApiKey {ELASTIC_API_KEY}",
}
