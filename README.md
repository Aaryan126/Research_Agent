# Research Orchestration System

Synthesizing findings across dozens of papers into a literature review takes researchers weeks. The Research Orchestration System runs three Google ADK agents with Gemini on Vertex AI: a researcher, peer reviewer, and claim verifier. They use ADK function tools to query the existing Elasticsearch paper corpus. The indexing pipeline converts PDFs into searchable chunks, so another corpus can be used after indexing it.

## Architecture

```
[React Frontend]  ── Vite + Tailwind chat UI (Netlify)
       |
       | HTTPS (SSE streaming)
       v
[FastAPI Backend]  ── GCP VM + Caddy reverse proxy
       |--- /api/research  (REST API — SSE streaming, literature review)
       |--- /api/verify    (REST API — SSE streaming, claim verification)
       |--- /mcp           (MCP endpoint for Claude Desktop)
       |--- /slack/*        (Slack bot — OAuth / slash commands)
       |
       v
[Google ADK + Gemini on Vertex AI]
       |--- Research Agent              (searches corpus, writes reviews)
       |--- Peer Review Agent           (checks evidence, issues verdicts)
       |--- Claim Verification Agent    (verifies claims against corpus)
       |            |
       |            v
[Elastic Cloud / Elasticsearch]  ── ADK function tools
       |--- papers_metadata index       (~200 papers — titles, abstracts, embeddings)
       |--- papers_chunks index         (~5000 chunks — full-text passages + embeddings)
```

## Access Points

| Interface | URL / Command |
|---|---|
| **Web App** | https://elasticresearchagent.netlify.app |
| **MCP (Claude Desktop)** | Add connector: `https://elasticresearchagent.duckdns.org/mcp` |
| **Slack** | `/research <topic>` or `/check-claim <claim>` after installing via [Add to Slack](https://elasticresearchagent.duckdns.org/slack/install) |
| **REST API** | `POST /api/research` (literature review) or `POST /api/verify` (claim verification) |

## How It Works

### Research Agent

Runs a six-step pipeline:

- Plans sub-questions from user's query
- Scopes the corpus using Elasticsearch aggregations
- Identifies key papers by citation count
- Retrieves evidence using full-text search across paper chunks
- Cross-checks findings for contradictions by running targeted searches for opposing evidence
- Synthesizes everything into a structured literature review with inline citations and confidence tags ([SUPPORTED], [CONTESTED], [INSUFFICIENT])

### Review Agent

Evaluates research draft through seven verification steps:

- Checks structural completeness
- Batch-verifies all referenced paper IDs against paper metadata
- Audits confidence tags by verifying each claim
- Spot-checks quantitative claims against source text
- Identifies missing high-impact papers by comparing cited references against the most cited papers for the topic
- Validates contradictions by independently searching corpus
- Issues final verdict: 'PASS' or 'REVISION_NEEDED'

The Research Agent and Review Agent operate in an orchestrated loop; if the reviewer finds draft unsatisfactory, it sends back specific, actionable feedback, and the Research Agent revises accordingly, up to two iterations.

### Claim Verification Agent

Evaluates a specific claim against the corpus through a five-step pipeline:

- Parses the claim into testable statements
- Finds relevant papers using search queries with varied terminology
- Gathers evidence and classifies each excerpt as SUPPORTS, CONTRADICTS, or QUALIFIES
- Assesses nuances by searching for methodological differences and scope limitations
- Produces structured verdict with confidence level

Each ADK agent receives six Elasticsearch function tools for paper search, metadata
verification, citation ranking, corpus statistics, and publication trends. FastAPI
orchestrates the loop and streams tool activity and final responses via SSE.

## Project Structure

```
├── server/
│   ├── main.py              # FastAPI entry point (REST + MCP + Slack routes)
│   ├── mcp_server.py         # MCP server (research_literature_review + research_draft + verify_claim tools)
│   ├── config.py              # Environment config, agent IDs, headers
│   ├── routers/
│   │   └── research.py        # POST /api/research + /api/verify — SSE streaming endpoints
│   └── services/
│       ├── agent.py           # Google ADK agents and SSE adapter
│       ├── corpus_tools.py    # Elasticsearch tools for ADK
│       ├── orchestrator.py    # Research-review loop + claim verification orchestrator
│       └── workflow.py        # Elastic Workflows API client (legacy)
│
├── frontend/                  # React + Vite + Tailwind chat UI
│   └── src/
│       ├── App.tsx            # Main app with chat state management
│       ├── hooks/
│       │   └── useResearchStream.ts  # SSE client hook
│       └── components/        # Header, Sidebar, ChatContainer, ReasoningTrace, etc.
│
├── slack_bot/
│   ├── bolt_app.py            # Slack Bolt app with OAuth (multi-workspace)
│   ├── handlers.py            # /research + /check-claim slash command handlers
│   └── formatting.py          # Markdown → Slack mrkdwn conversion
│
├── workflows/
│   ├── research_review_loop.yaml  # Elastic Workflows YAML (3-iteration loop)
│   └── peer_review.yaml          # Standalone peer review workflow
│
├── config.py                  # Elasticsearch client config (for indexing scripts)
├── setup_indexes.py           # Creates papers_metadata + papers_chunks indexes
├── load_metadata.py           # Indexes paper metadata with abstract embeddings
├── parse_pdfs.py              # Extracts, chunks, and sections PDF text
├── index_chunks.py            # Embeds and indexes parsed chunks
├── run_indexing.py            # Orchestrates the full ingestion pipeline
├── test_search.py             # Validates keyword, vector, and ES|QL queries
├── evaluate_reports.py        # Measures report quality against the corpus
├── app.py                     # Streamlit frontend (legacy, replaced by React app)
│
├── reports/                   # Auto-saved literature review reports
├── tests/
│   └── test_mcp_server.py     # MCP server unit tests
│
├── DEPLOYMENT.md              # Full deployment guide (GCP, Caddy, Netlify, DNS)
├── SLACK.md                   # Slack bot setup and troubleshooting
├── TOOLS.md                   # Historical Elastic Agent Builder tool documentation
├── EVALUATION.md              # Evaluation metrics and interpretation guide
└── PROGRESS.md                # Development progress tracker
```

## Elasticsearch Indexes

| Index | Documents | Purpose |
|---|---|---|
| **papers_metadata** | ~200 | Paper-level data: title, authors, abstract, year, citation count, keywords, abstract embedding (384d) |
| **papers_chunks** | ~5,000 | Chunked full-text passages (~385 words each) with embeddings for hybrid search |

Embeddings use `all-MiniLM-L6-v2` (384 dimensions, cosine similarity).

## Evaluation

`evaluate_reports.py` cross-references generated reports against the Elasticsearch corpus to measure:

| Metric | What It Measures |
|---|---|
| Citation Accuracy | Whether cited papers exist in the corpus (detects hallucinated references) |
| Claim Grounding | Whether quantitative claims can be traced to source text |
| Corpus Coverage | How many papers the agent cited out of the total corpus |
| Confidence Distribution | Balance of `[SUPPORTED]`, `[CONTESTED]`, `[INSUFFICIENT]` tags |
| Report Statistics | Word count, sections, references, research gaps, contradictions |

See [EVALUATION.md](EVALUATION.md) for detailed metrics explanation and interpretation.

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- A Google Cloud project with Vertex AI API enabled, model access, and Application Default Credentials
- Elasticsearch credentials and indexed `papers_metadata` and `papers_chunks` in `.env`

### Backend

```bash
cp .env.example .env
# Edit .env with your project ID, location and Elasticsearch credentials.
gcloud auth application-default login
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

The backend uses `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION`, and `GEMINI_MODEL` from `.env`. ADC supplies Google
credentials; no Google API key is needed. On a Google Cloud VM, attach a service
account with Vertex AI permissions. Test with `POST /api/research` using
`{"topic":"AI agent reliability","mode":"research"}` or `mode:"verify"`.
The SSE stream reports agent starts, corpus tool calls/results, final text and verdicts.
It does not expose Gemini's private reasoning.

`app.py` and `server/services/workflow.py` are legacy Elastic workflow interfaces;
the FastAPI, MCP and Slack paths use the ADK backend in `server/services/agent.py`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:5173` and proxies API requests to `http://localhost:8000`.

### Data Ingestion (Bring Your Own Corpus)

The indexing pipeline converts any collection of PDFs into searchable, embedded chunks in Elasticsearch. Place your PDFs in the `data/` directory and run:

```bash
python setup_indexes.py    # Create ES indexes with embedding mappings
python run_indexing.py      # Load metadata, parse PDFs, chunk text, generate embeddings, index
python test_search.py       # Validate keyword, vector, and ES|QL search
```

The pipeline handles PDF parsing, text chunking (~385 words), embedding generation (all-MiniLM-L6-v2, 384d), and indexing into two Elasticsearch indexes (papers_metadata + papers_chunks). The agents then work over whatever corpus is indexed.

## Deployment

The previous deployment used a GCP VM, Caddy, DuckDNS and Netlify. Set the Vertex AI environment variables and attach an authorized service account before deploying this version. Vertex AI model calls and Elasticsearch have separate usage charges. See [DEPLOYMENT.md](DEPLOYMENT.md) for the earlier infrastructure setup; its Elastic Agent Builder steps are historical.

## Documentation

| File | Contents |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | GCP VM, Caddy, DuckDNS, Netlify, server management |
| [SLACK.md](SLACK.md) | Slack bot OAuth setup, slash command configuration |
| [TOOLS.md](TOOLS.md) | Historical Elastic Agent Builder tools and search strategy |
| [EVALUATION.md](EVALUATION.md) | Report quality metrics, benchmarks, interpretation |
| [PROGRESS.md](PROGRESS.md) | Development history and phase-by-phase progress |
