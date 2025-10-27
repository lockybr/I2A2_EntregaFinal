"""Reprocess all documents stored in backend/api/documents_db.json

Usage:
  python reprocess_all.py [--dry-run]

Notes:
- Run this script from the project root or backend folder where Python environment is configured.
- Make sure the process that serves the API (uvicorn) is stopped before running this script to avoid file contention.
- Ensure OPENROUTER_API_KEY (or equivalent) is exported in the environment for LLM calls.
"""
import os
import json
import argparse
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.joinpath('api', 'documents_db.json')


def main(dry_run: bool = False, delay: float = 0.5):
    if not DB_PATH.exists():
        print(f"Documents DB not found at {DB_PATH}")
        return 1

    # warn if no API key set
    if not os.environ.get('OPENROUTER_API_KEY') and not os.environ.get('OPENAI_API_KEY'):
        print("Warning: OPENROUTER_API_KEY or OPENAI_API_KEY not set in environment. LLM calls may fail.")

    print(f"Loading DB from {DB_PATH}")
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    ids = [k for k in db.keys()]
    print(f"Found {len(ids)} documents in DB")

    # Import process_document from api.main on demand (after checking DB exists)
    print("Importing processing function from backend.api.main ...")
    try:
        # adjust sys.path so import works even when running from project root
        import sys
        repo_root = Path(__file__).parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from api.main import process_document
    except Exception as e:
        print("Failed to import process_document from api.main:", e)
        return 2

    processed = 0
    skipped = 0
    errors = 0

    for doc_id in ids:
        rec = db.get(doc_id)
        tmp_path = rec.get('tmp_path') if isinstance(rec, dict) else None
        filename = rec.get('filename') if isinstance(rec, dict) else None
        if not tmp_path or not filename:
            print(f"Skipping {doc_id}: missing tmp_path or filename")
            skipped += 1
            continue
        if not Path(tmp_path).exists():
            print(f"Skipping {doc_id}: tmp_path file not found: {tmp_path}")
            skipped += 1
            continue

        print(f"Processing {doc_id} -> file: {tmp_path}")
        if dry_run:
            processed += 1
            continue

        try:
            # call the same function used by the API to process a document (synchronous)
            process_document(doc_id, tmp_path, filename)
            processed += 1
        except Exception as e:
            print(f"Error processing {doc_id}: {e}")
            errors += 1
        # small delay to avoid overloading
        time.sleep(delay)

    print('\nDone.')
    print(f"Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='List documents that would be processed without running')
    parser.add_argument('--delay', type=float, default=0.5, help='Seconds to wait between documents')
    args = parser.parse_args()
    exit(main(dry_run=args.dry_run, delay=args.delay))
