"""Parse PDF files into text chunks mapped to paper IDs."""

import json
import os
import re
import unicodedata

import fitz
from tqdm import tqdm

from config import PAPERS_PDF_DIR

METADATA_JSON = os.path.join(
    PAPERS_PDF_DIR, "AI_Agent_Architectures_and_Frameworks.json"
)
OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "parsed_chunks.json"
)

CHUNK_TARGET_WORDS = 385
OVERLAP_WORDS = 38

SECTION_MAP = {
    "introduction": "introduction",
    "methods": "methods",
    "methodology": "methods",
    "method": "methods",
    "approach": "methods",
    "proposed method": "methods",
    "proposed approach": "methods",
    "experimental setup": "methods",
    "experiment": "methods",
    "experiments": "methods",
    "results": "results",
    "evaluation": "results",
    "experimental results": "results",
    "discussion": "discussion",
    "analysis": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "concluding remarks": "conclusion",
    "summary": "conclusion",
    "related work": "related_work",
    "related works": "related_work",
    "literature review": "related_work",
    "background": "background",
    "preliminaries": "background",
    "preliminary": "background",
    "overview": "background",
    "abstract": "abstract",
}

HEADING_RE = re.compile(
    r"^(?:"
    r"(?:[0-9]+\.?\s+)"           # "1. Introduction" or "1 Introduction"
    r"|(?:[IVXLC]+\.?\s+)"        # "II. METHODS"
    r"|(?:[A-Z]\.?\s+)"           # "A. Approach" (letter-based)
    r")?"
    r"(.+)$"
)

ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z\s:&\-]{3,}$")


def normalize_title(title):
    """Normalize a title for matching: lowercase, strip colons/punctuation, collapse whitespace."""
    title = unicodedata.normalize("NFKD", title)
    title = title.replace(":", " ").replace("–", "-").replace("—", "-")
    title = re.sub(r"[^\w\s-]", "", title.lower())
    title = re.sub(r"\s+", " ", title).strip()
    return title


def build_title_map(metadata):
    """Build normalized_title_prefix -> paper_id mapping."""
    title_map = {}
    for paper in metadata:
        norm = normalize_title(paper["title"])
        title_map[norm] = paper["paperId"]
    return title_map


def match_pdf_to_paper(pdf_filename, title_map):
    """Match a PDF filename to a paper_id using prefix matching."""
    name = pdf_filename.rsplit(".pdf", 1)[0]
    norm_pdf = normalize_title(name)

    # Try exact match first
    if norm_pdf in title_map:
        return title_map[norm_pdf]

    # Prefix match: PDF name (possibly truncated) matches start of metadata title
    for norm_title, paper_id in title_map.items():
        if norm_title.startswith(norm_pdf) or norm_pdf.startswith(norm_title):
            return paper_id

    return None


def clean_text(text):
    """Clean extracted PDF text: fix hyphenation, collapse whitespace."""
    # Fix hyphenated line breaks (e.g., "multi-\nagent" -> "multiagent")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Fix regular line breaks mid-sentence
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_references(text):
    """Remove everything after the last References/Bibliography heading."""
    pattern = re.compile(
        r"\n\s*(?:References|Bibliography|REFERENCES|BIBLIOGRAPHY)\s*\n",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if matches:
        return text[: matches[-1].start()].strip()
    return text


def detect_section(line):
    """Detect if a line is a section heading and return normalized section type."""
    line_stripped = line.strip()
    if not line_stripped or len(line_stripped) > 100:
        return None

    # Check all-caps headings
    if ALL_CAPS_RE.match(line_stripped):
        heading_text = line_stripped.lower().strip()
        for key, section in SECTION_MAP.items():
            if key in heading_text:
                return section
        return None

    match = HEADING_RE.match(line_stripped)
    if match:
        heading_text = match.group(1).strip().lower()
        # Remove trailing numbering artifacts
        heading_text = re.sub(r"\s*\d+$", "", heading_text).strip()
        for key, section in SECTION_MAP.items():
            if heading_text == key or heading_text.startswith(key):
                return section

    return None


def split_into_sentences(text):
    """Split text into sentences at period/question/exclamation boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s for s in sentences if s.strip()]


def chunk_text(text, target_words=CHUNK_TARGET_WORDS, overlap_words=OVERLAP_WORDS):
    """Chunk text into ~target_words pieces with overlap, splitting at sentence boundaries."""
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_words = []
    current_count = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)

        if current_count + word_count > target_words and current_count > 0:
            chunks.append(" ".join(current_words))
            # Keep overlap from end of current chunk
            overlap = current_words[-overlap_words:] if len(current_words) > overlap_words else current_words[:]
            current_words = overlap + words
            current_count = len(current_words)
        else:
            current_words.extend(words)
            current_count += word_count

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def extract_and_chunk_pdf(pdf_path):
    """Extract text from PDF, detect sections, and return chunks."""
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  Warning: Cannot open PDF: {e}")
        return []

    full_text = ""
    for page in doc:
        page_text = page.get_text()
        if page_text:
            full_text += page_text + "\n"
    doc.close()

    if not full_text.strip():
        print("  Warning: PDF has no extractable text")
        return []

    full_text = clean_text(full_text)
    full_text = remove_references(full_text)

    # Split into lines to detect sections
    lines = full_text.split("\n")
    sections = []
    current_section = "body"
    current_text = []

    for line in lines:
        section = detect_section(line)
        if section:
            if current_text:
                sections.append((current_section, " ".join(current_text)))
            current_section = section
            current_text = []
        else:
            if line.strip():
                current_text.append(line.strip())

    if current_text:
        sections.append((current_section, " ".join(current_text)))

    # Chunk each section
    all_chunks = []
    for section_type, section_text in sections:
        if not section_text.strip():
            continue
        text_chunks = chunk_text(section_text)
        for chunk in text_chunks:
            all_chunks.append({
                "section_type": section_type,
                "chunk_text": chunk,
            })

    return all_chunks


def main():
    """Parse all PDFs and output parsed_chunks.json."""
    print("=" * 60)
    print("PARSE PDFs")
    print("=" * 60)

    with open(METADATA_JSON, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print(f"Loaded {len(metadata)} metadata entries")

    title_map = build_title_map(metadata)

    pdf_dir = PAPERS_PDF_DIR
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDF files")

    all_chunks = []
    matched = 0
    skipped_no_match = 0
    skipped_empty = 0

    for pdf_file in tqdm(pdf_files, desc="Parsing PDFs"):
        paper_id = match_pdf_to_paper(pdf_file, title_map)
        if not paper_id:
            print(f"\n  Warning: No metadata match for '{pdf_file[:80]}...'")
            skipped_no_match += 1
            continue

        pdf_path = os.path.join(pdf_dir, pdf_file)
        chunks = extract_and_chunk_pdf(pdf_path)

        if not chunks:
            skipped_empty += 1
            continue

        matched += 1
        for i, chunk in enumerate(chunks):
            chunk_id = f"{paper_id}_chunk_{i:04d}"
            all_chunks.append({
                "chunk_id": chunk_id,
                "paper_id": paper_id,
                "chunk_text": chunk["chunk_text"],
                "section_type": chunk["section_type"],
                "chunk_index": i,
            })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False)

    summary = {
        "papers_parsed": matched,
        "total_chunks": len(all_chunks),
        "skipped_no_match": skipped_no_match,
        "skipped_empty": skipped_empty,
        "output_file": OUTPUT_PATH,
    }
    print(f"\nParsed {matched} PDFs → {len(all_chunks)} chunks")
    print(f"Skipped: {skipped_no_match} no match, {skipped_empty} empty/unreadable")
    print(f"Output: {OUTPUT_PATH}")
    return summary


if __name__ == "__main__":
    main()
