"""Utility to create a sanitized copy of backend/api/documents_db.json suitable for committing.

It will:
- Load the existing documents_db.json (if present)
- For each document record, remove 'tmp_path' and any keys that contain absolute user-local paths
- Replace absolute Windows paths in string fields with a placeholder '<ABSOLUTE_PATH_REDACTED>'
- Write the sanitized JSON to backend/api/documents_db.sanitized.json and report counts

Run from repository root with: python scripts/sanitize_documents_db.py
"""
import json
import os
import re
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(REPO_ROOT, 'backend', 'api', 'documents_db.json')
OUT_PATH = os.path.join(REPO_ROOT, 'backend', 'api', 'documents_db.sanitized.json')

WINDOWS_ABS_RE = re.compile(r'([A-Za-z]:\\[^\n\r\t\"]*)')
POSIX_ABS_RE = re.compile(r'(/[^\s\n\r\t\"]+)')

if not os.path.exists(DB_PATH):
    print(f"No documents DB found at {DB_PATH}")
    raise SystemExit(1)

with open(DB_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

sanitized = {}
removed_tmp = 0
replaced_paths = 0
for k, rec in data.items():
    if not isinstance(rec, dict):
        sanitized[k] = rec
        continue
    newrec = dict(rec)
    # remove tmp_path if present
    if 'tmp_path' in newrec:
        newrec['tmp_path'] = None
        removed_tmp += 1
    # scan all string fields and redact absolute paths
    def redact_obj(o):
        global replaced_paths
        if isinstance(o, str):
            s = o
            s2 = WINDOWS_ABS_RE.sub('<ABSOLUTE_PATH_REDACTED>', s)
            s2 = POSIX_ABS_RE.sub('<ABSOLUTE_PATH_REDACTED>', s2)
            if s2 != s:
                replaced_paths += 1
            return s2
        elif isinstance(o, list):
            return [redact_obj(i) for i in o]
        elif isinstance(o, dict):
            return {ik: redact_obj(iv) for ik, iv in o.items()}
        else:
            return o
    newrec = redact_obj(newrec)
    sanitized[k] = newrec

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(sanitized, f, ensure_ascii=False, indent=2)

print(f"Sanitized DB written to {OUT_PATH}")
print(f"Records processed: {len(data)}; tmp_path removed from {removed_tmp} records; {replaced_paths} string fields redacted.")
print("If the sanitized file looks good, you can replace the repo's documents_db.json with it before pushing.")

# Optionally create a timestamped backup
bak = DB_PATH + '.bak_for_sanitize_' + datetime.now().strftime('%Y%m%d_%H%M%S')
try:
    os.rename(DB_PATH, bak)
    os.rename(OUT_PATH, DB_PATH)
    print(f"Replaced original DB with sanitized DB; original moved to {bak}")
except Exception:
    print("Left sanitized copy in place; original DB unchanged.")
