"""Reprocess only documents that currently contain the 'User not found' LLM 401 error.

This script reads backend/api/documents_db.json, finds records whose raw_extracted or
extracted_error contains the 401 marker, and calls process_document(doc_id, tmp_path, filename)
for each one. It reuses the same process_document used by the API to ensure consistent behavior.

Run from repo root like:
  python .\backend\reprocess_selected.py
"""
import json
import time
from pathlib import Path
import sys

DB_PATH = Path(__file__).parent.joinpath('api', 'documents_db.json')
if not DB_PATH.exists():
    print(f"DB not found at {DB_PATH}")
    sys.exit(1)

print(f"Loading DB from {DB_PATH}")
with open(DB_PATH, 'r', encoding='utf-8') as f:
    db = json.load(f)

# find bad keys
bad = []
for k, v in db.items():
    re = v.get('raw_extracted')
    ee = v.get('extracted_error')
    ed = v.get('extracted_data')
    if isinstance(re, str) and 'User not found' in re:
        bad.append(k)
        continue
    if isinstance(ee, str) and 'User not found' in ee:
        bad.append(k)
        continue
    if isinstance(ed, str) and 'User not found' in ed:
        bad.append(k)
        continue

if not bad:
    print('No problematic documents found.')
    sys.exit(0)

print(f"Found {len(bad)} documents to reprocess")

# Import process_document from api.main
try:
    # Ensure backend is importable
    repo_root = Path(__file__).parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from api.main import process_document
except Exception as e:
    print('Failed to import process_document from api.main:', e)
    sys.exit(2)

processed = 0
errors = 0
for doc_id in bad:
    rec = db.get(doc_id)
    tmp_path = rec.get('tmp_path') if isinstance(rec, dict) else None
    filename = rec.get('filename') if isinstance(rec, dict) else None
    if not tmp_path or not filename:
        print(f"Skipping {doc_id}: missing tmp_path or filename")
        continue
    if not Path(tmp_path).exists():
        print(f"Skipping {doc_id}: tmp_path file not found: {tmp_path}")
        continue
    print(f"Reprocessing {doc_id} -> {tmp_path}")
    try:
        process_document(doc_id, tmp_path, filename)
        processed += 1
    except Exception as e:
        print(f"Error processing {doc_id}: {e}")
        errors += 1
    time.sleep(0.5)

print(f"Done. Processed: {processed}, Errors: {errors}")
