# Research Agent — Agent Configuration Documentation

## Overview

The Academic Research Agent is a multi-agent system built with Elastic Agent Builder that automates systematic literature reviews and claim verification over a corpus of ~200 academic papers on Agentic AI. It combines LLM reasoning with Elasticsearch-powered search, analytics, and verification to produce structured, cited reports.

The system uses three specialized agents — a Researcher, a Peer Reviewer, and a Claim Verifier — orchestrated by a Python backend that streams real-time reasoning traces to a React frontend.

Two modes are available:
- **Literature Review** — Research Agent writes a draft, Peer Review Agent evaluates it, up to 2 iterations until PASS
- **Claim Verification** — Claim Verification Agent evaluates a specific claim against the corpus (single pass, no peer review)

---

## Architecture

The backend directly calls the Elastic Agent Builder `converse/async` streaming API for each agent. There is no orchestrator agent or workflow YAML — the Python backend handles the research-review loop, forwarding agent reasoning events to the frontend in real-time via Server-Sent Events (SSE).

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER                                      │
│              React Frontend (localhost:5173)                      │
│              "Review research on [topic]" or "Verify [claim]"    │
└──────────────────────────┬───────────────────────────────────────┘
                           │  POST /api/research
                           │  SSE stream response
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   PYTHON BACKEND (FastAPI)                        │
│              Orchestrates research-review loop + claim verification│
│              Streams reasoning events via SSE                    │
│                                                                   │
│  Literature Review mode (up to 2 iterations):                    │
│                                                                   │
│  ┌──────────────────┐          ┌──────────────────────────┐      │
│  │ RESEARCHER AGENT  │  draft   │   PEER REVIEW AGENT      │      │
│  │ 6-step pipeline   │────────▶│   7-step pipeline         │      │
│  │ 14-22 tool calls  │         │   7-12 tool calls         │      │
│  │                   │◀────────│   VERDICT + ISSUES        │      │
│  └──────────────────┘ feedback  └──────────────────────────┘      │
│         │       ▲                                                  │
│         │       │  REVISION_NEEDED? Loop (max 2 iterations)      │
│         │       └─────────────────────────────────────             │
│         │                                                          │
│         │  PASS? → Return final report                            │
│                                                                   │
│  Claim Verification mode (single pass):                          │
│                                                                   │
│  ┌────────────────────────────┐                                   │
│  │ CLAIM VERIFICATION AGENT    │                                   │
│  │ 5-step pipeline             │ → Return verification report    │
│  │ 8-12 tool calls             │                                   │
│  └────────────────────────────┘                                   │
└─────────┼──────────────────────────────────────────────────────────┘
           │  Converse streaming API
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                 ELASTIC AGENT BUILDER                             │
│           Converse/Async Streaming API (SSE)                     │
│                                                                   │
│  Each agent call streams events:                                 │
│  reasoning → tool_call → tool_result → message_chunk             │
└─────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       ELASTICSEARCH                               │
│                                                                   │
│  ┌───────────────────────┐    ┌────────────────────────────────┐ │
│  │    papers_metadata     │    │        papers_chunks            │ │
│  │    (~200 papers)       │    │        (~5000 passages)         │ │
│  │                        │    │                                 │ │
│  │  title          text   │    │  chunk_text          text      │ │
│  │  authors       keyword │    │  chunk_embedding     384d vec  │ │
│  │  year          integer │    │  section_type        keyword   │ │
│  │  citation_count integer│    │  paper_id            keyword   │ │
│  │  abstract       text   │    │  chunk_index         integer   │ │
│  │  abstract_embedding    │    │                                 │ │
│  │              384d vec  │    │  Hybrid search:                │ │
│  │  keywords     keyword  │    │  BM25 keyword + kNN vector     │ │
│  │  source_venue keyword  │    │                                 │ │
│  └───────────────────────┘    └────────────────────────────────┘ │
│                                                                   │
│  Linked by paper_id (foreign key relationship)                   │
│  All three agents query the same corpus independently            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agents (3 total)

### 1. Researcher Agent

| Field | Value |
|---|---|
| **Agent ID** | `research_literature_review_agent` |
| **Display Name** | Academic Research Agent |
| **Model** | Claude Sonnet 4.5 |
| **Display Description** | An AI-powered literature review assistant that searches, analyzes, and synthesizes academic research papers on Agentic AI. Ask a research question and get a structured report with citations, trends, contradictions, and research gaps. |

### 2. Peer Review Agent

| Field | Value |
|---|---|
| **Agent ID** | `peer_review_agent` |
| **Display Name** | Peer Review Agent |
| **Model** | Claude Sonnet 4.5 |
| **Display Description** | Reviews literature review reports for structural completeness, citation accuracy, and evidence quality by independently verifying claims against the Elasticsearch corpus. |

### 3. Claim Verification Agent

| Field | Value |
|---|---|
| **Agent ID** | `claim_verification_agent` |
| **Display Name** | Claim Verification Agent |
| **Model** | Claude Sonnet 4.5 |
| **Display Description** | Verifies whether specific claims, trends, or findings from academic papers are corroborated or contradicted by other research in the Elasticsearch corpus. Produces structured verification reports with verdicts, evidence, and confidence assessments. |

---

## Backend Orchestration

The Python backend (`server/services/orchestrator.py`) manages two workflows:

### Literature Review Flow (`POST /api/research` with `mode=research`)

1. Receives the user's research topic
2. Calls the Researcher Agent via the Elastic converse streaming API
3. Forwards all reasoning events (thinking, tool calls, results) to the frontend in real-time
4. Collects the researcher's final output and extracts cited paper_ids from the References section
5. Calls the Peer Review Agent with the draft and the pre-extracted paper_ids list
6. Forwards the reviewer's reasoning events to the frontend
7. Parses the reviewer's verdict (`PASS` or `REVISION_NEEDED`)
8. If `REVISION_NEEDED`, sends the draft + feedback back to the Researcher for revision
9. Loops for up to 2 iterations or until `PASS`
10. Returns the final report and review to the frontend

### Claim Verification Flow (`POST /api/research` with `mode=verify`, or `POST /api/verify`)

1. Receives the user's claim text
2. Calls the Claim Verification Agent via the Elastic converse streaming API
3. Forwards all reasoning events to the frontend in real-time
4. Returns the verification report (single pass, no peer review loop)

### SSE Event Types (Backend → Frontend)

| Event | Data | When |
|-------|------|------|
| `agent_start` | `{agent, agent_id, iteration}` | Agent call begins |
| `reasoning` | `{text, agent, iteration}` | Agent thinking step |
| `tool_call` | `{tool_id, params, agent, iteration}` | Agent calling a tool |
| `tool_result` | `{tool_id, results, agent, iteration}` | Tool result returned |
| `tool_progress` | `{tool_call_id, message, agent, iteration}` | Tool execution progress |
| `message_chunk` | `{text, agent, iteration}` | Agent generating final output |
| `agent_end` | `{agent, iteration}` | Agent call complete |
| `verdict` | `{verdict, iteration}` | Peer review verdict |
| `result` | `{report, review, iteration_info, iterations}` | Final results |
| `error` / `done` | `{message}` / `{}` | Error / stream complete |

### Key Backend Files

| File | Purpose |
|---|---|
| `server/config.py` | Agent IDs (researcher, reviewer, verifier), max iterations (2), timeouts, Elastic API headers |
| `server/services/agent.py` | Elastic converse streaming client — calls `POST /api/agent_builder/converse/async` |
| `server/services/orchestrator.py` | Research-review loop + claim verification logic, SSE event formatting |
| `server/routers/research.py` | FastAPI endpoints (`/api/research`, `/api/verify`), StreamingResponse wrapper |

---

## Researcher Agent: System Instructions

The agent operates under the following instructions that define its behavior, workflow, and output format:

```
IMPORTANT: Execute all six steps in order within a single response. Show your step-by-step
reasoning in the reasoning/thinking trace only. Your visible response to the user should
ONLY contain the final compiled literature review report from Step 6 — do not include
Step 1 plan, Step 2 corpus stats, or any intermediate step outputs in the visible response.
The report itself should contain all relevant information (research landscape, findings,
contradictions, gaps, references).

You are an Academic Research Literature Review Agent. You conduct systematic, multi-step
literature reviews over a corpus of ~200 academic papers about Agentic AI indexed in
Elasticsearch.

When a user provides a research topic or question, follow these steps in order:

STEP 1 — PLAN
Break the user's topic into 3-5 specific sub-questions. For each sub-question, identify
the key search terms you will use.

STEP 2 — SCOPE THE CORPUS
Use the Corpus Overview tool to understand the size and distribution of available research.
Use the Publication Trends tool to check how much research exists on the topic over time.

STEP 3 — IDENTIFY KEY PAPERS
Use the Top Cited Papers tool and Search Paper Metadata tool to find the most relevant and
influential papers for each sub-question. Note paper_ids for later deep-dive retrieval.

STEP 4 — RETRIEVE EVIDENCE
Use the Search Research Papers tool to retrieve specific passages from paper chunks. Run
separate searches for each sub-question using different queries. Look for specific claims,
methods, results, and numbers. Always note the paper_id and section_type of evidence you find.

STEP 5 — VERIFY AND CROSS-CHECK
For each major claim or finding, run additional targeted searches to find contradicting
evidence. Specifically search for papers that disagree with or challenge the claim.
Classify each finding as:
- SUPPORTED: Multiple papers agree
- CONTESTED: Papers present conflicting evidence
- INSUFFICIENT: Only one source, needs more research

STEP 6 — SYNTHESIZE AND REPORT
Compile your findings into a structured literature review report with these sections:
1. Introduction — topic overview and scope
2. Research Landscape — corpus statistics and publication trends
3. Key Findings — organized by subtopic cluster, with citations (paper title + year)
4. Contradictions and Debates — areas where papers disagree, with evidence from both sides
5. Research Gaps — topics with thin coverage or insufficient evidence
6. Suggested Future Research Directions

RULES:
- Always cite papers inline using format: (Paper Title, Author et al., Year).
  Example: (Cognitive Architectures for Language Agents, Yao et al., 2023)
- At the end of the report, include a numbered References section listing every cited
  paper with: full title, all authors, year, and paper_id.
- If you find conflicting evidence, present both sides fairly.
- Never fabricate paper titles or citations. Only cite papers you found in the corpus.
- If you have a paper_id but are missing the author names, use the Search Paper Metadata
  tool to look up the full author list before including it in the report. If you cannot
  retrieve author names, cite using the paper title and year only — never use "Anonymous"
  as an author name.
- When you cannot find enough evidence, say so explicitly rather than speculating.
- Use multiple different search queries rather than relying on a single search.
- Label every claim in Key Findings with a confidence tag: [SUPPORTED], [CONTESTED],
  or [INSUFFICIENT] based on the evidence found in Step 5.
```

---

## Researcher Agent: Six-Step Workflow

### Step 1 — Plan (Pure LLM Reasoning)

- **Tools used:** None (LLM reasoning only)
- **Input:** User's research topic or question
- **Action:** Decomposes the topic into 3–5 specific sub-questions with associated search terms
- **Output:** Research plan with sub-questions (visible in reasoning trace)

### Step 2 — Scope the Corpus (ES|QL Analytics)

- **Tools used:** `research.corpus_overview`, `research.publication_trends`
- **Input:** Research plan from Step 1
- **Action:** Retrieves corpus-wide statistics (total papers, papers per year, citation averages) and topic-specific publication trends
- **Output:** Corpus landscape data (used in final report's Research Landscape section)

### Step 3 — Identify Key Papers (Metadata Search + ES|QL)

- **Tools used:** `research.top_cited`, `research.search_metadata`
- **Input:** Sub-questions and search terms from Step 1
- **Action:** Finds the most cited and relevant papers for each sub-question using metadata search and citation ranking
- **Output:** List of key papers with paper_ids noted for deep retrieval

### Step 4 — Retrieve Evidence (Full-Text Chunk Search)

- **Tools used:** `research.search_papers`
- **Input:** Sub-questions, search terms, and key paper_ids from Steps 1 and 3
- **Action:** Runs multiple targeted searches across paper chunks to retrieve specific claims, methods, results, and quantitative data
- **Output:** Collection of evidence passages with paper_id and section_type attribution

### Step 5 — Verify and Cross-Check (Contradiction Search)

- **Tools used:** `research.search_papers`, `research.search_metadata`
- **Input:** Major claims and findings from Step 4
- **Action:** For each major claim, runs additional searches specifically looking for contradicting evidence
- **Output:** Each claim classified as SUPPORTED, CONTESTED, or INSUFFICIENT

### Step 6 — Synthesize and Report (LLM Reasoning)

- **Tools used:** None (LLM synthesis only)
- **Input:** All evidence and classifications from Steps 1–5
- **Action:** Compiles everything into a structured literature review report
- **Output:** Complete literature review with 7 sections including References

---

## Peer Review Agent: Seven-Step Pipeline

### Step 1 — Structural Completeness (LLM Reasoning)

- **Tools used:** None
- **Action:** Checks that all 7 required report sections are present
- **Issue severity:** Missing section → CRITICAL

### Step 2 — Reference Verification (Batch ES|QL Query)

- **Tools used:** `platform.core.execute_esql`
- **Action:** Collects all paper_ids from the References section and verifies them in a single batch ES|QL query (`FROM papers_metadata | WHERE paper_id IN (...) | KEEP paper_id, title, year`). Compares results against the report's references for existence and metadata accuracy.
- **Issue severity:** Non-existent paper_id or metadata mismatch → CRITICAL

### Step 3 — Confidence Tag Audit (LLM Reasoning)

- **Tools used:** None
- **Action:** Verifies every claim in Key Findings has a confidence tag and the tag usage is reasonable
- **Issue severity:** Untagged claim → MAJOR

### Step 4 — Evidence Spot-Check (Full-Text Search)

- **Tools used:** `research.search_papers`
- **Action:** Selects 3-5 key quantitative claims and independently searches the corpus to verify they exist
- **Issue severity:** Unverifiable claim → MAJOR

### Step 5 — Coverage Gap Analysis (ES|QL Analytics)

- **Tools used:** `research.top_cited`
- **Action:** Finds the most-cited papers for the topic and compares against the pre-extracted cited paper_ids list (provided by the orchestrator at the top of the reviewer prompt) to identify missing high-impact papers
- **Issue severity:** Missing high-impact paper → MINOR

### Step 6 — Contradiction Validation (Full-Text Search)

- **Tools used:** `research.search_papers`
- **Action:** Verifies that contradictions cited in the report are genuine disagreements
- **Issue severity:** False contradiction → MAJOR

### Step 7 — Gap-Direction Alignment (LLM Reasoning)

- **Tools used:** None
- **Action:** Checks that each Suggested Future Research Direction ties back to a specific gap
- **Issue severity:** Unsupported direction → MINOR

### Peer Review Output Format

```
VERDICT: [PASS or REVISION_NEEDED]

ISSUES:
- [CRITICAL/MAJOR/MINOR] <section>: <description>
  Evidence: <what was found or not found in Elasticsearch>

MISSED_PAPERS:
- <paper title> (paper_id: <id>, citations: <count>) — relevant because: <reason>

SUMMARY:
<2-3 sentence assessment>
```

**Verdict rules:**
- Any CRITICAL issue → REVISION_NEEDED
- 1+ MAJOR issues → REVISION_NEEDED
- Only MINOR issues → PASS
- No issues → PASS

---

## Claim Verification Agent: Five-Step Pipeline

### Step 1 — Parse the Claim (LLM Reasoning)

- **Tools used:** None
- **Action:** Breaks compound claims into individual testable statements, identifies subject, predicate, and key search terms

### Step 2 — Find Relevant Papers (Search + ES|QL)

- **Tools used:** `research.search_papers`, `research.search_metadata`, `research.top_cited`
- **Action:** Runs at least 3 search queries per statement using varied terminology to find papers discussing the claim's topic

### Step 3 — Gather Evidence For and Against (Full-Text Search)

- **Tools used:** `research.search_papers`
- **Action:** Retrieves specific passages from relevant papers and classifies each as SUPPORTS, CONTRADICTS, or QUALIFIES

### Step 4 — Assess Conditions and Nuance (Targeted Search)

- **Tools used:** `research.search_papers`
- **Action:** For QUALIFIES evidence, runs additional searches to understand conditions, methodological differences, temporal trends, and scope mismatches

### Step 5 — Compile Verification Report (LLM Synthesis)

- **Tools used:** None
- **Action:** Produces a structured Claim Verification Report

### Claim Verification Output Format

```
# Claim Verification Report

## 1. Claim Under Review
[The exact claim]
**Verdict: [VERDICT] · Confidence: [LEVEL]**

## 2. Corroborating Evidence
[Papers that support the claim with specific findings]

## 3. Contradicting Evidence
[Papers that challenge the claim with specific findings]

## 4. Nuances and Conditions
[Context-dependent findings, methodological caveats, scope limitations]

## 5. Confidence Assessment
[Summary: corroborating vs contradicting count, corpus coverage, evidence quality]

## 6. References
[All cited papers with full details and paper_ids]
```

**Verdict values:** STRONGLY SUPPORTED, PARTIALLY SUPPORTED, MIXED EVIDENCE, WEAKLY CONTRADICTED, CONTRADICTED, INSUFFICIENT EVIDENCE

**Confidence levels:** HIGH, MODERATE, LOW

---

## Assigned Tools

All three agents share the same 5 custom tools and 6 platform tools:

### Custom Tools

| Tool ID | Type | Purpose |
|---|---|---|
| `research.search_papers` | Index search (`papers_chunks`) | Retrieve specific evidence passages from full-text paper chunks |
| `research.search_metadata` | Index search (`papers_metadata`) | Find papers by topic, author, year, venue |
| `research.publication_trends` | ES\|QL | Count papers per year for a given topic |
| `research.top_cited` | ES\|QL | Find most influential papers ranked by citation count |
| `research.corpus_overview` | ES\|QL | Statistical overview of the entire research corpus |

### Platform Tools (Built-in)

| Tool ID | Purpose |
|---|---|
| `platform.core.search` | General-purpose search fallback across Elasticsearch |
| `platform.core.get_document_by_id` | Retrieve full document by ID |
| `platform.core.execute_esql` | Execute arbitrary ES\|QL queries |
| `platform.core.generate_esql` | Generate ES\|QL from natural language |
| `platform.core.get_index_mapping` | Inspect index structure |
| `platform.core.list_indices` | Discover available indices |

---

## Tool Call Patterns

### Literature Review Mode

A typical end-to-end research review triggers 21-34 tool calls across both agents:

```
RESEARCHER AGENT (14-22 calls):
research.corpus_overview              → 1 call    (Step 2)
research.publication_trends           → 2-3 calls (Step 2)
research.top_cited                    → 2-3 calls (Step 3)
research.search_metadata              → 2-3 calls (Step 3)
research.search_papers                → 5-8 calls (Step 4)
research.search_papers                → 2-4 calls (Step 5)

PEER REVIEW AGENT (7-12 calls):
platform.core.execute_esql            → 1 call    (Step 2: batch reference verification)
research.search_papers                → 3-5 calls (Step 4)
research.top_cited                    → 1-2 calls (Step 5)
research.search_papers                → 2-3 calls (Step 6)
─────────────────────────────────────────────────
Total per iteration                   → 21-34 calls
```

If a revision is needed, the Researcher runs again with the review feedback (another 14-22 calls).

### Claim Verification Mode

A typical claim verification triggers 8-12 tool calls in a single pass:

```
CLAIM VERIFICATION AGENT (8-12 calls):
research.top_cited                    → 1 call    (Step 2)
research.search_papers                → 3-4 calls (Step 2)
research.search_metadata              → 1-2 calls (Step 2)
research.search_papers                → 2-3 calls (Step 3)
research.search_papers                → 1-2 calls (Step 4)
platform.core.get_document_by_id      → 0-1 calls (metadata lookup)
─────────────────────────────────────────────────
Total                                 → 8-12 calls
```

---

## Output Format

### Literature Review

The Research Agent produces a structured literature review with these sections:

### 1. Introduction
Topic overview, scope definition, and relevance statement.

### 2. Research Landscape
Corpus statistics (total papers, year distribution, citation averages) and topic-specific publication trends.

### 3. Key Findings
Organized by subtopic clusters. Each claim includes:
- Confidence tag: **[SUPPORTED]**, **[CONTESTED]**, or **[INSUFFICIENT]**
- Inline citations: (Paper Title, Author et al., Year)
- Specific quantitative evidence where available

### 4. Contradictions and Debates
Areas where papers present conflicting evidence, with arguments from both sides.

### 5. Research Gaps
Topics with thin coverage, single-source claims, or insufficient evidence.

### 6. Suggested Future Research Directions
Actionable research questions derived from identified gaps and contradictions.

### 7. References
Numbered list of every cited paper with: full title, all authors, year, and paper_id.

### Claim Verification

The Claim Verification Agent produces a structured report with these sections:

1. **Claim Under Review** — The exact claim with verdict and confidence on a single line
2. **Corroborating Evidence** — Papers supporting the claim with specific findings
3. **Contradicting Evidence** — Papers challenging the claim with specific findings
4. **Nuances and Conditions** — Context-dependent findings, caveats, scope limitations
5. **Confidence Assessment** — Evidence summary (counts, corpus coverage, quality)
6. **References** — All cited papers with full details and paper_ids

---

## Frontend

The React frontend provides a chat-style interface with real-time reasoning trace visibility:

- **Empty state:** Centered "How can I help you?" prompt with a mode selector toggle (Literature Review / Verify Claim) and input bar
- **During processing:** Active agent indicator with a collapsible reasoning trace showing thinking steps, tool calls, and results in real-time
- **Complete state:** Reasoning trace (collapsed, clickable to review), followed by the full report rendered in markdown with PDF download

### Key Frontend Files

| File | Purpose |
|---|---|
| `frontend/src/App.tsx` | Main app, state management, stream callback wiring |
| `frontend/src/hooks/useResearchStream.ts` | SSE stream consumer, event dispatching |
| `frontend/src/components/ReasoningTrace.tsx` | Combined reasoning trace with agent dividers |
| `frontend/src/components/AssistantMessage.tsx` | Message rendering (traces, verdicts, report) |
| `frontend/src/components/MarkdownRenderer.tsx` | Markdown rendering for the final report |

---

## Measurable Impact

| Metric | Manual Process | With Agent |
|---|---|---|
| Time to complete literature review | 2-4 weeks | 1-2 minutes |
| Time to verify a claim | Hours of manual searching | 1-2 minutes |
| Papers analyzed per review | 20-30 (human limit) | 100-200 (full corpus) |
| Cross-reference checks | Limited by time | Systematic for every claim |
| Contradiction detection | Often missed | Automated with targeted searches |
| Citation consistency | Error-prone | Enforced by tool-based retrieval |
| Reproducibility | Low (subjective) | High (same tools, same corpus) |
