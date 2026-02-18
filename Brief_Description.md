# Research Orchestration System — Multi-Agent Literature Review and Claim Verification

Synthesizing findings across dozens of papers into a literature review takes researchers weeks. Cross-checking whether a specific claim holds up across the broader literature is equally time-consuming. The Research Orchestration System automates both tasks using three multi-step agents built using Elastic Agent Builder. These are specialized agents that search, synthesise, review, and verify each other's work. Currently running on ~200 Agentic AI papers (~5,000 full-text chunks) indexed in Elasticsearch, the system is corpus-agnostic. The included indexing pipeline converts any collection of PDFs into searchable, embedded chunks.

## Research Agent

Runs a six-step pipeline:

- Plans sub-questions from user's query
- Scopes the corpus using ES|QL analytics
- Identifies key papers by citation count
- Retrieves evidence using hybrid keyword + semantic search across full-text chunks
- Cross-checks findings for contradictions by running targeted searches for opposing evidence
- Synthesizes everything into a structured literature review with inline citations and confidence tags ([SUPPORTED], [CONTESTED], [INSUFFICIENT])

## Review Agent

Evaluates research draft through seven verification steps:

- Checks structural completeness
- Batch-verifies all references exist via ES|QL
- Audits confidence tags by verifying each claim
- Spot-checks quantitative claims against source text
- Identifies missing high-impact papers by comparing cited references against the most cited papers for the topic
- Validates contradictions by independently searching corpus
- Issues final verdict: 'PASS' or 'REVISION_NEEDED'

The Research Agent and Review Agent operate in an orchestrated loop; if the reviewer finds draft unsatisfactory, it sends back specific, actionable feedback, and the Research Agent revises accordingly, up to two iterations.

## Claim Verification Agent

Evaluates a specific claim against the corpus through a five-step pipeline:

- Parses the claim into testable statements
- Finds relevant papers using search queries with varied terminology
- Gathers evidence and classifies each excerpt as SUPPORTS, CONTRADICTS, or QUALIFIES
- Assesses nuances by searching for methodological differences and scope limitations
- Produces structured verdict with confidence level

Each agent uses 5 custom tools (2 index searches, 3 ES|QL tools) plus default platform tools. A FastAPI backend orchestrates the agent loop, streaming real-time reasoning traces via SSE. Accessible through three interfaces: a React web app, Slack (/research, /check-claim), and Claude Code via MCP.

**Features used:** Elastic Agent Builder, custom index search tools, custom ES|QL tools, platform tools (execute_esql, search, get_document_by_id), converse streaming API, MCP.

**What I liked:** ES|QL tools were powerful for structured analytics like publication trends and batch reference verification, complementing the unstructured search tools well. The converse streaming API made it straightforward to build a real-time reasoning trace UI that builds trust in the output.

**Challenge:** Getting the Review Agent to verify citations efficiently. Initially, the reviewer made individual Elasticsearch queries for each reference, 15+ tool calls just for citation checking. Restructuring this into a single batch ES|QL query with the orchestrator pre-extracting paper_ids from the draft reduced verification to one tool call, cutting review time significantly.
