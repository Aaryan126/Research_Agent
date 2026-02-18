# Research Orchestration System

Synthesizing findings across dozens of papers into a literature review takes researchers weeks. Cross-checking whether a specific claim holds up across the broader literature is equally time-consuming. The Research Orchestration System automates both tasks using three multi-step agents built using Elastic Agent Builder. These are specialized agents that search, synthesise, review, and verify each other's work. Currently running on ~200 Agentic AI papers (~5,000 full-text chunks) indexed in Elasticsearch, the system is corpus-agnostic. The included indexing pipeline converts any collection of PDFs into searchable, embedded chunks.

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
[Elastic Cloud]  ── Agent Builder
       |--- Research Agent              (searches corpus, writes reviews)
       |--- Peer Review Agent           (evaluates drafts, issues verdicts)
       |--- Claim Verification Agent    (verifies claims against corpus)
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
- Scopes the corpus using ES|QL analytics
- Identifies key papers by citation count
- Retrieves evidence using hybrid keyword + semantic search across full-text chunks
- Cross-checks findings for contradictions by running targeted searches for opposing evidence
- Synthesizes everything into a structured literature review with inline citations and confidence tags ([SUPPORTED], [CONTESTED], [INSUFFICIENT])

### Review Agent

Evaluates research draft through seven verification steps:

- Checks structural completeness
- Batch-verifies all references exist via ES|QL
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

Each agent uses 5 custom tools (2 index searches, 3 ES|QL tools) plus default platform tools. A FastAPI backend orchestrates the agent loop, streaming real-time reasoning traces via SSE.

## Project Structure

```
├── server/
│   ├── main.py              # FastAPI entry point (REST + MCP + Slack routes)
│   ├── mcp_server.py         # MCP server (research_literature_review + research_draft + verify_claim tools)
│   ├── config.py              # Environment config, agent IDs, headers
│   ├── routers/
│   │   └── research.py        # POST /api/research + /api/verify — SSE streaming endpoints
│   └── services/
│       ├── agent.py           # Elastic Agent Builder streaming client
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
├── TOOLS.md                   # Custom Elastic Agent Builder tools documentation
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
- Elasticsearch credentials in `.env`

### Backend

```bash
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

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

The system runs on a GCP e2-micro VM (Always Free tier) with Caddy for HTTPS, DuckDNS for DNS, and Netlify for the frontend. Total cost is ~$0-4/month (mostly GCP external IP). See [DEPLOYMENT.md](DEPLOYMENT.md) for full details.

## Documentation

| File | Contents |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | GCP VM, Caddy, DuckDNS, Netlify, server management |
| [SLACK.md](SLACK.md) | Slack bot OAuth setup, slash command configuration |
| [TOOLS.md](TOOLS.md) | Custom Elastic Agent Builder tools and search strategy |
| [EVALUATION.md](EVALUATION.md) | Report quality metrics, benchmarks, interpretation |
| [PROGRESS.md](PROGRESS.md) | Development history and phase-by-phase progress |
