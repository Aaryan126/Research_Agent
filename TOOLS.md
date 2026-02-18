# Research Agent — Custom Tools Documentation

## Overview

This document describes all custom tools created in Elastic Agent Builder for the Academic Research Literature Review Agent. The agent uses these tools to search, analyze, and synthesize research papers about Agentic AI indexed in Elasticsearch.

There are two Elasticsearch indexes powering these tools:

- **`papers_chunks`** — Full-text passages (~500 token chunks) extracted from ~200 research paper PDFs. Each chunk includes the text, a vector embedding, the section type (introduction, methods, results, etc.), and a link back to its parent paper via `paper_id`.
- **`papers_metadata`** — One document per paper containing title, authors, year, abstract, citation count, keywords, venue, and an abstract embedding vector.

---

## Tool 1: Search Research Papers

| Field | Value |
|---|---|
| **Tool ID** | `research.search_papers` |
| **Type** | Index search |
| **Target Pattern** | `papers_chunks` |
| **Row Limit** | 20 |

**Description:**
Search through full-text chunks of academic research papers about agentic AI. Use this tool when you need to find specific claims, evidence, methodology details, or results from papers. Returns relevant passages with paper_id and section_type. Use this for retrieving evidence to support or contradict specific claims.

**Custom Instructions:**
Always include paper_id and section_type in results. The chunk_text field contains the main content. Use chunk_index to maintain reading order within a paper. When searching for claims or evidence, prioritize results from section_type 'results' and 'discussion'. When searching for methodology, prioritize section_type 'methods'.

**How it works:**
- Accepts natural language queries from the agent
- Automatically performs hybrid search (keyword + semantic vector) across paper chunks
- Returns the most relevant passages from across the entire corpus
- Each result includes the paper_id (to trace back to the source paper) and section_type

**Example queries:**
- "What methods are used to reduce hallucination in multi-agent systems?"
- "Evidence for retrieval augmented generation improving factual accuracy"
- "Experimental results comparing single-agent vs multi-agent architectures"

---

## Tool 2: Search Paper Metadata

| Field | Value |
|---|---|
| **Tool ID** | `research.search_metadata` |
| **Type** | Index search |
| **Target Pattern** | `papers_metadata` |
| **Row Limit** | 50 |

**Description:**
Search paper metadata including titles, authors, abstracts, year, citation counts, and keywords. Use this tool to find papers by author, year, venue, or topic at a high level. Use this before deep-diving into paper chunks to identify which papers are relevant. Also use for citation count comparisons and identifying highly-cited foundational work.

**Custom Instructions:**
Always include paper_id, title, year, citation_count, and authors in results. The abstract field contains paper summaries. Use keywords field for topic filtering. Sort by citation_count when looking for influential papers.

**How it works:**
- Accepts natural language queries
- Searches across paper titles, abstracts, authors, keywords, and other metadata fields
- Can dynamically generate ES|QL queries for structured filtering (e.g., filtering by year or sorting by citation count)
- Returns high-level paper information without full-text content

**Example queries:**
- "What are the most cited papers about AI agent architectures?"
- "Find papers by Shunyu Yao"
- "Papers published in 2025 about multi-agent security"

---

## Tool 3a: Publication Trends

| Field | Value |
|---|---|
| **Tool ID** | `research.publication_trends` |
| **Type** | ES|QL |

**Description:**
Counts papers published per year for a given topic. Use this to identify research trends, growth areas, or declining interest in specific topics over time.

**ES|QL Query:**
```esql
FROM papers_metadata
| WHERE MATCH(abstract, ?search_topic)
| STATS paper_count = COUNT(*) BY year
| SORT year ASC
| LIMIT 20
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `search_topic` | string | Yes | The research topic or keywords to analyze publication trends for, e.g. 'multi-agent systems' or 'hallucination mitigation' |

**Example output:**
```
paper_count | year
-----------+-----
     1     | 2020
     2     | 2023
    11     | 2024
    94     | 2025
     7     | 2026
```

---

## Tool 3b: Top Cited Papers

| Field | Value |
|---|---|
| **Tool ID** | `research.top_cited` |
| **Type** | ES|QL |

**Description:**
Finds the most influential papers on a given topic ranked by citation count. Use this to identify foundational or highly-referenced work in a research area.

**ES|QL Query:**
```esql
FROM papers_metadata
| WHERE MATCH(abstract, ?search_topic)
| KEEP paper_id, title, year, citation_count, authors
| SORT citation_count DESC
| LIMIT ?max_results
```

**Parameters:**

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `search_topic` | string | Yes | — | The research topic or keywords to find highly cited papers for, e.g. 'agent architectures' or 'tool use' |
| `max_results` | integer | No | 10 | Maximum number of papers to return, sorted by citation count |

**Example output:**
```
paper_id    | title                                          | year | citation_count | authors
------------+------------------------------------------------+------+----------------+--------
e4bb1b...   | Cognitive Architectures for Language Agents     | 2023 | 296            | [Yao, ...]
25ae2f...   | The Landscape of Emerging AI Agent Arch...      | 2024 | 149            | [Masterman, ...]
```

---

## Tool 3c: Corpus Overview

| Field | Value |
|---|---|
| **Tool ID** | `research.corpus_overview` |
| **Type** | ES|QL |

**Description:**
Provides a statistical overview of the entire research corpus. Shows total papers, papers per year, and average citation counts. Use this at the start of a literature review to understand the scope and distribution of available research.

**ES|QL Query:**
```esql
FROM papers_metadata
| STATS total_papers = COUNT(*), avg_citations = AVG(citation_count), max_citations = MAX(citation_count) BY year
| SORT year ASC
| LIMIT 20
```

**Parameters:** None

**Example output:**
```
total_papers | avg_citations | max_citations | year
-------------+---------------+---------------+-----
     1       |  24.0         |  24           | 2020
     2       | 179.0         | 296           | 2023
    11       |  31.6         | 149           | 2024
   101       |   9.6         | 197           | 2025
     7       |   0.9         |   5           | 2026
```

---

## Tool Usage Strategy

The agent follows this general pattern when using tools:

1. **Start broad** — Use `research.corpus_overview` to understand what data is available
2. **Identify trends** — Use `research.publication_trends` to see how the topic evolved
3. **Find key papers** — Use `research.top_cited` to identify foundational work
4. **Discover relevant papers** — Use `research.search_metadata` to find papers matching specific criteria
5. **Deep dive** — Use `research.search_papers` to retrieve specific evidence, claims, and methodology details from paper chunks
6. **Cross-check** — Use `research.search_papers` again with targeted queries to find contradicting or supporting evidence for specific claims

---

## Index Schemas

### papers_metadata
| Field | Type | Purpose |
|---|---|---|
| paper_id | keyword | Unique identifier, links to chunks |
| title | text | Full-text searchable paper title |
| authors | keyword | Exact match filtering and aggregation |
| year | integer | Temporal filtering |
| abstract | text | Full-text searchable abstract |
| abstract_embedding | dense_vector (384 dims) | Semantic/kNN search |
| citation_count | integer | Quality/influence ranking |
| keywords | keyword | Topic filtering and aggregation |
| source_venue | keyword | Conference/journal filtering |
| doi | keyword | Unique paper reference |
| url | keyword | Link to paper |

### papers_chunks
| Field | Type | Purpose |
|---|---|---|
| chunk_id | keyword | Unique chunk identifier |
| paper_id | keyword | Links chunk to parent paper |
| chunk_text | text | Full-text searchable passage content |
| chunk_embedding | dense_vector (384 dims) | Semantic/kNN search |
| section_type | keyword | Section label (introduction, methods, results, discussion, conclusion, body) |
| chunk_index | integer | Reading order within a paper |