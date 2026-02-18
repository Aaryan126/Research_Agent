"""Evaluation script for Academic Research Agent report quality.

Cross-references generated literature review reports against Elasticsearch
indexes to measure citation accuracy, claim grounding, corpus coverage,
confidence tag distribution, and report statistics.
"""

import argparse
import json
import os
import re
import sys

from config import get_es_client

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
METADATA_INDEX = "papers_metadata"
CHUNKS_INDEX = "papers_chunks"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def read_report(filepath):
    """Read report text from a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def split_references_section(text):
    """Split report into body and references section.

    Returns (body, references_text). If no references section is found,
    references_text is an empty string.
    """
    pattern = re.compile(
        r"^(?:#{0,3}\s*)?(?:\d+\.\s*)?References\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return text[: match.start()], text[match.start():]
    return text, ""


def parse_references(references_text):
    """Extract individual references with paper_id and title when available.

    Returns a list of dicts: {raw, paper_id, title}
    """
    if not references_text.strip():
        return []

    lines = references_text.strip().splitlines()
    # Skip the header line itself
    content_lines = []
    for line in lines:
        if re.match(r"^(?:#{0,3}\s*)?(?:\d+\.\s*)?References\s*$", line, re.IGNORECASE):
            continue
        content_lines.append(line)

    # Join and split into individual references.
    # References are separated by blank lines or start with a number.
    joined = "\n".join(content_lines).strip()
    # Split on blank-line boundaries that precede a new reference
    ref_blocks = re.split(r"\n\s*\n", joined)

    refs = []
    for block in ref_blocks:
        block = block.strip()
        if not block:
            continue

        paper_id = None
        title = None

        # Extract paper_id — two known formats:
        #   *Paper ID: <hash>*   or   paper_id: <hash>
        pid_match = re.search(
            r"(?:\*\s*)?[Pp]aper[\s_][Ii][Dd][:\s]+([a-f0-9]{20,})(?:\s*\*)?",
            block,
        )
        if pid_match:
            paper_id = pid_match.group(1).strip()

        # Extract title — look for italicized title (*Title*) or the text
        # after "(<year>). " up to the next period or Paper ID marker.
        title_match = re.search(
            r"\(\d{4}\)\.\s*(.+?)(?:\.\s*(?:\*?\s*[Pp]aper|paper_id)|$)",
            block,
            re.DOTALL,
        )
        if title_match:
            candidate = title_match.group(1).strip().rstrip(".")
            # Remove markdown italics
            candidate = candidate.replace("*", "").strip()
            if len(candidate) > 10:
                title = candidate

        # Fallback: grab first substantial sentence as title
        if not title:
            sentences = re.split(r"\.\s", block)
            for s in sentences:
                clean = re.sub(r"^\d+\.\s*", "", s).strip()
                clean = clean.replace("*", "").strip()
                if len(clean) > 15 and "paper_id" not in clean.lower():
                    title = clean
                    break

        refs.append({"raw": block, "paper_id": paper_id, "title": title})

    return refs


def extract_quantitative_claims(body_text):
    """Find quantitative claims in report body text.

    Looks for percentages, multipliers, specific counts with units, and
    decimal numbers in context. Returns list of {claim, context}.
    """
    claims = []
    seen_contexts = set()

    patterns = [
        r"\d+\.?\d*\s*%",             # percentages: 26.1%, 96%
        r"\d+\.?\d*\s*×",             # multipliers: 28×, 2.12×
        r"\d+\.?\d*x\s+(?:more|reduction|improvement|faster|slower)",
        r"\b\d{2,}(?:,\d{3})*\s+(?:papers?|citations?|attacks?|skills?|scenarios?|agents?|CVEs?|users?)",
        r"\b\d+\.?\d+\s+(?:vs|versus)\s+\d+\.?\d+",  # comparisons: 94.8% vs 93.4%
        r"(?:achieved|showed|demonstrated|found|reported|reduced|improved)\s+.*?\d+\.?\d*\s*%",
        r"\$\d+\.?\d*",               # dollar amounts
        r"OR\s*=\s*\d+\.?\d*",        # odds ratios
        r"p\s*<\s*0\.\d+",            # p-values
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, body_text, re.IGNORECASE):
            start = max(0, match.start() - 120)
            end = min(len(body_text), match.end() + 120)
            context = body_text[start:end].strip()
            # Normalize whitespace
            context = re.sub(r"\s+", " ", context)

            # Deduplicate overlapping contexts
            claim_text = match.group(0).strip()
            dedup_key = claim_text + context[len(context) // 3: 2 * len(context) // 3]
            if dedup_key not in seen_contexts:
                seen_contexts.add(dedup_key)
                claims.append({"claim": claim_text, "context": context})

    return claims


def extract_context_words(context, n=10):
    """Extract ~n meaningful words around a quantitative claim for search."""
    # Remove numbers/symbols to focus on descriptive words
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", context)
    words = [w for w in cleaned.split() if len(w) > 2]
    # Take words from the middle of the context for best relevance
    mid = len(words) // 2
    start = max(0, mid - n // 2)
    return " ".join(words[start: start + n])


def count_confidence_tags(text):
    """Count occurrences of confidence tags.

    Handles both bracketed ([SUPPORTED]) and unbracketed (SUPPORTED:) formats.
    """
    tags = {
        "[SUPPORTED]": 0,
        "[CONTESTED]": 0,
        "[INSUFFICIENT]": 0,
    }
    for tag in tags:
        keyword = tag.strip("[]")
        # Count bracketed form: [SUPPORTED]
        bracketed = len(re.findall(re.escape(tag), text))
        # Count unbracketed form at start of line or after whitespace: SUPPORTED:
        unbracketed = len(re.findall(
            r"(?<!\[)\b" + keyword + r"\b(?!\])",
            text,
        ))
        # Avoid double-counting: unbracketed matches also fire on "[SUPPORTED]"
        # so subtract bracketed from unbracketed
        tags[tag] = bracketed + max(0, unbracketed - bracketed)
    return tags


def count_sections(text):
    """Count main sections in the report.

    Counts top-level sections: '## N. Title' markdown headers, or plain
    'N. Title' lines that look like section headers (not numbered list items).
    """
    has_markdown_headers = bool(re.search(r"^#{2}\s+\d+\.", text, re.MULTILINE))

    if has_markdown_headers:
        # Markdown report: count ## headers (with or without numbers)
        pattern = r"^#{2}\s+(?:\d+\.\s+)?\S.+$"
    else:
        # Plain text report: count 'N. Title' lines that aren't sub-sections
        # (no X.Y numbering) and don't contain bold markdown (**)
        pattern = r"^(\d+)\.\s+[A-Z][^*\n]+$"

    return len(re.findall(pattern, text, re.MULTILINE))


def count_section_items(text, section_name):
    """Count bullet points or numbered items in a named section."""
    # Find the section
    pattern = re.compile(
        r"^(?:#{0,3}\s*)?(?:\d+\.?\s*)?.*?" + re.escape(section_name) + r".*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return 0

    # Find the next top-level section after this one
    section_start = match.end()
    next_section = re.search(
        r"^(?:#{2,3}\s+\d*\.?\s*[A-Z]|\d+\.\s+[A-Z])",
        text[section_start:],
        re.MULTILINE,
    )
    if next_section:
        section_text = text[section_start: section_start + next_section.start()]
    else:
        section_text = text[section_start:]

    # Count sub-sections (### X.Y or X.Y Title patterns) as items
    subsection_matches = re.findall(
        r"^(?:#{3,4}\s+)?\d+\.\d+\s+.+$",
        section_text,
        re.MULTILINE,
    )
    if subsection_matches:
        return len(subsection_matches)

    # Fallback: count bullet points or numbered items
    items = re.findall(r"^\s*[-•*]\s+.+$|^\s*\d+\.\s+.+$", section_text, re.MULTILINE)
    return len(items)


def extract_paper_ids_from_references(refs):
    """Get unique paper_ids from parsed references."""
    return {r["paper_id"] for r in refs if r["paper_id"]}


# ---------------------------------------------------------------------------
# Elasticsearch verification
# ---------------------------------------------------------------------------

def verify_citation_by_paper_id(es, paper_id):
    """Check if a paper_id exists in papers_metadata. Returns True/False."""
    try:
        result = es.search(
            index=METADATA_INDEX,
            body={"query": {"term": {"paper_id": paper_id}}, "size": 1},
        )
        return result["hits"]["total"]["value"] > 0
    except Exception as e:
        print(f"    [ERROR] paper_id lookup failed: {e}")
        return False


def verify_citation_by_title(es, title):
    """Search for a title in papers_metadata. Returns True/False."""
    try:
        result = es.search(
            index=METADATA_INDEX,
            body={"query": {"match": {"title": title}}, "size": 1},
        )
        if result["hits"]["total"]["value"] > 0:
            score = result["hits"]["hits"][0]["_score"]
            return score > 5.0  # threshold for meaningful match
        return False
    except Exception as e:
        print(f"    [ERROR] title lookup failed: {e}")
        return False


def verify_claim_in_corpus(es, context_words):
    """Search papers_chunks for text matching the claim context."""
    try:
        result = es.search(
            index=CHUNKS_INDEX,
            body={"query": {"match": {"chunk_text": context_words}}, "size": 1},
        )
        if result["hits"]["total"]["value"] > 0:
            score = result["hits"]["hits"][0]["_score"]
            return score > 8.0  # threshold for meaningful match
        return False
    except Exception as e:
        print(f"    [ERROR] claim lookup failed: {e}")
        return False


def get_total_corpus_papers(es):
    """Get total paper count from papers_metadata."""
    try:
        result = es.count(index=METADATA_INDEX)
        return result["count"]
    except Exception as e:
        print(f"  [ERROR] corpus count failed: {e}")
        return 0


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate_report(filepath, es):
    """Run all evaluations on a single report file."""
    filename = os.path.basename(filepath)
    text = read_report(filepath)
    body, refs_text = split_references_section(text)
    refs = parse_references(refs_text)

    print(f"\n{'=' * 54}")
    print(f"  EVALUATION: {filename}")
    print(f"{'=' * 54}")

    # --- 1. Citation Verification ---
    print("\n  Checking citations...")
    verified_by_id = 0
    verified_by_title = 0
    not_found = 0
    hallucinated = []

    for i, ref in enumerate(refs, 1):
        label = ref["title"][:50] if ref["title"] else ref["raw"][:50]
        if ref["paper_id"]:
            if verify_citation_by_paper_id(es, ref["paper_id"]):
                verified_by_id += 1
                print(f"    [{i}/{len(refs)}] ID verified: {label}...")
            else:
                # Fallback to title
                if ref["title"] and verify_citation_by_title(es, ref["title"]):
                    verified_by_title += 1
                    print(f"    [{i}/{len(refs)}] Title matched: {label}...")
                else:
                    not_found += 1
                    hallucinated.append(ref["raw"][:100])
                    print(f"    [{i}/{len(refs)}] NOT FOUND: {label}...")
        elif ref["title"]:
            if verify_citation_by_title(es, ref["title"]):
                verified_by_title += 1
                print(f"    [{i}/{len(refs)}] Title matched: {label}...")
            else:
                not_found += 1
                hallucinated.append(ref["raw"][:100])
                print(f"    [{i}/{len(refs)}] NOT FOUND: {label}...")
        else:
            not_found += 1
            hallucinated.append(ref["raw"][:100])
            print(f"    [{i}/{len(refs)}] UNPARSEABLE: {ref['raw'][:50]}...")

    total_citations = len(refs)
    verified_total = verified_by_id + verified_by_title
    citation_accuracy = (verified_total / total_citations * 100) if total_citations else 0.0

    # --- 2. Claim Grounding ---
    print("\n  Checking quantitative claims...")
    claims = extract_quantitative_claims(body)
    grounded = 0
    unverified_claims = []

    for i, claim in enumerate(claims, 1):
        context_words = extract_context_words(claim["context"])
        if verify_claim_in_corpus(es, context_words):
            grounded += 1
            print(f"    [{i}/{len(claims)}] Grounded: {claim['claim']}")
        else:
            unverified_claims.append(claim["claim"])
            print(f"    [{i}/{len(claims)}] Unverified: {claim['claim']}")

    total_claims = len(claims)
    grounding_rate = (grounded / total_claims * 100) if total_claims else 0.0

    # --- 3. Corpus Coverage ---
    print("\n  Checking corpus coverage...")
    unique_ids = extract_paper_ids_from_references(refs)
    total_corpus = get_total_corpus_papers(es)
    coverage = (len(unique_ids) / total_corpus * 100) if total_corpus else 0.0

    # --- 4. Confidence Tag Distribution ---
    tags = count_confidence_tags(text)
    total_tags = sum(tags.values())

    # --- 5. Report Statistics ---
    word_count = len(text.split())
    sections = count_sections(text)
    num_references = len(refs)
    research_gaps = count_section_items(text, "Research Gaps")
    contradictions = count_section_items(text, "Contradictions")

    # --- 6. Print summary ---
    print(f"\n{'=' * 54}")
    print(f"  EVALUATION: {filename}")
    print(f"{'=' * 54}")

    print(f"\n  CITATION ACCURACY")
    print(f"    Total citations:            {total_citations}")
    print(f"    Verified by paper_id:       {verified_by_id}")
    print(f"    Verified by title match:    {verified_by_title}")
    print(f"    Not found:                  {not_found}")
    print(f"    Citation accuracy:          {citation_accuracy:.1f}%")
    print(f"    Hallucinated citations:     {not_found}")

    print(f"\n  CLAIM GROUNDING")
    print(f"    Quantitative claims found:  {total_claims}")
    print(f"    Verified in corpus:         {grounded}")
    print(f"    Unverified:                 {total_claims - grounded}")
    print(f"    Grounding rate:             {grounding_rate:.1f}%")

    print(f"\n  CORPUS COVERAGE")
    print(f"    Unique papers cited:        {len(unique_ids)}")
    print(f"    Total papers in corpus:     {total_corpus}")
    print(f"    Coverage per review:        {coverage:.1f}%")

    print(f"\n  CONFIDENCE DISTRIBUTION")
    for tag, count in tags.items():
        pct = (count / total_tags * 100) if total_tags else 0.0
        print(f"    {tag}:{' ' * (24 - len(tag))}{count} ({pct:.1f}%)")

    print(f"\n  REPORT STATISTICS")
    print(f"    Word count:                 {word_count:,}")
    print(f"    Sections:                   {sections}")
    print(f"    References:                 {num_references}")
    print(f"    Research gaps:              {research_gaps}")
    print(f"    Contradictions:             {contradictions}")

    print(f"\n{'=' * 54}")

    # Build results dict
    results = {
        "file": filename,
        "citation_accuracy": {
            "total_citations": total_citations,
            "verified_by_paper_id": verified_by_id,
            "verified_by_title_match": verified_by_title,
            "not_found": not_found,
            "citation_accuracy_pct": round(citation_accuracy, 1),
            "hallucinated_citations": hallucinated,
        },
        "claim_grounding": {
            "total_quantitative_claims": total_claims,
            "verified_in_corpus": grounded,
            "unverified": total_claims - grounded,
            "grounding_rate_pct": round(grounding_rate, 1),
            "unverified_claims": unverified_claims,
        },
        "corpus_coverage": {
            "unique_papers_cited": len(unique_ids),
            "total_papers_in_corpus": total_corpus,
            "coverage_pct": round(coverage, 1),
        },
        "confidence_distribution": {
            tag: {"count": count, "pct": round((count / total_tags * 100) if total_tags else 0, 1)}
            for tag, count in tags.items()
        },
        "report_statistics": {
            "word_count": word_count,
            "sections": sections,
            "references": num_references,
            "research_gaps": research_gaps,
            "contradictions": contradictions,
        },
    }

    # Save JSON
    base = os.path.splitext(filename)[0]
    json_path = os.path.join(REPORTS_DIR, f"{base}_eval.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved to {json_path}")

    return results


def print_aggregate(all_results):
    """Print aggregate summary across multiple reports."""
    n = len(all_results)
    if n == 0:
        return

    avg_citation = sum(r["citation_accuracy"]["citation_accuracy_pct"] for r in all_results) / n
    avg_grounding = sum(r["claim_grounding"]["grounding_rate_pct"] for r in all_results) / n
    avg_papers = sum(r["corpus_coverage"]["unique_papers_cited"] for r in all_results) / n
    avg_words = sum(r["report_statistics"]["word_count"] for r in all_results) / n

    # Total unique papers across all reports
    all_ids = set()
    for r in all_results:
        json_path = os.path.join(REPORTS_DIR, f"{os.path.splitext(r['file'])[0]}_eval.json")
        # We already have unique count per report; collect from citations
    total_corpus = all_results[0]["corpus_coverage"]["total_papers_in_corpus"]

    # Recalculate total unique from individual paper_id sets isn't stored,
    # so sum individual counts as approximation (may double-count shared refs)
    total_unique_approx = sum(r["corpus_coverage"]["unique_papers_cited"] for r in all_results)

    avg_supported = sum(
        r["confidence_distribution"]["[SUPPORTED]"]["count"] for r in all_results
    ) / n
    avg_contested = sum(
        r["confidence_distribution"]["[CONTESTED]"]["count"] for r in all_results
    ) / n
    avg_insufficient = sum(
        r["confidence_distribution"]["[INSUFFICIENT]"]["count"] for r in all_results
    ) / n

    print(f"\n{'=' * 54}")
    print(f"  AGGREGATE SUMMARY ({n} reports)")
    print(f"{'=' * 54}")
    print(f"  Avg citation accuracy:         {avg_citation:.1f}%")
    print(f"  Avg claim grounding:           {avg_grounding:.1f}%")
    print(f"  Avg papers cited per review:   {avg_papers:.0f}")
    print(f"  Avg word count:                {avg_words:,.0f}")
    print(f"  Total unique papers cited:     {total_unique_approx} / {total_corpus}")
    print(f"  Avg [SUPPORTED] per review:    {avg_supported:.0f}")
    print(f"  Avg [CONTESTED] per review:    {avg_contested:.0f}")
    print(f"  Avg [INSUFFICIENT] per review: {avg_insufficient:.0f}")
    print(f"{'=' * 54}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Research Agent literature review reports."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="Path to a single report .txt file")
    group.add_argument(
        "--all", action="store_true", help="Evaluate all .txt reports in reports/"
    )
    args = parser.parse_args()

    print("Connecting to Elasticsearch...")
    es = get_es_client()
    if not es.ping():
        print("ERROR: Cannot connect to Elasticsearch.")
        sys.exit(1)
    print("Connected.\n")

    if args.file:
        if not os.path.isfile(args.file):
            print(f"ERROR: File not found: {args.file}")
            sys.exit(1)
        evaluate_report(args.file, es)
    else:
        txt_files = sorted(
            f
            for f in os.listdir(REPORTS_DIR)
            if f.endswith(".txt") and not f.endswith("_eval.json")
        )
        if not txt_files:
            print(f"No .txt report files found in {REPORTS_DIR}")
            sys.exit(1)

        all_results = []
        for fname in txt_files:
            fpath = os.path.join(REPORTS_DIR, fname)
            result = evaluate_report(fpath, es)
            all_results.append(result)

        print_aggregate(all_results)


if __name__ == "__main__":
    main()
