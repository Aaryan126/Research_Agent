"""Orchestrate the full ingestion pipeline: metadata → parse PDFs → index chunks."""

import time

from load_metadata import main as load_metadata_main
from parse_pdfs import main as parse_pdfs_main
from index_chunks import main as index_chunks_main


def main():
    print("=" * 60)
    print("RESEARCH AGENT — INGESTION PIPELINE")
    print("=" * 60)
    start = time.time()

    # Step 1: Load metadata (validates ES connection early)
    print("\n[Step 1/3] Loading paper metadata into Elasticsearch...\n")
    metadata_summary = load_metadata_main()

    # Step 2: Parse PDFs into chunks
    print("\n[Step 2/3] Parsing PDFs into text chunks...\n")
    parse_summary = parse_pdfs_main()

    # Step 3: Index chunks with embeddings
    print("\n[Step 3/3] Indexing chunks into Elasticsearch...\n")
    chunks_summary = index_chunks_main()

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = elapsed % 60

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Papers indexed:    {metadata_summary.get('papers_loaded', 0)}")
    print(f"Papers parsed:     {parse_summary.get('papers_parsed', 0)}")
    print(f"Total chunks:      {chunks_summary.get('chunks_indexed', 0)}")
    print(f"Metadata errors:   {metadata_summary.get('errors', 0)}")
    print(f"Chunk errors:      {chunks_summary.get('errors', 0)}")
    print(f"Skipped (no match):{parse_summary.get('skipped_no_match', 0)}")
    print(f"Skipped (empty):   {parse_summary.get('skipped_empty', 0)}")
    print(f"Total time:        {minutes}m {seconds:.1f}s")


if __name__ == "__main__":
    main()
