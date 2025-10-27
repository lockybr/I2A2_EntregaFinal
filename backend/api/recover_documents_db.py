"""Recover top-level entries from a corrupted documents_db.json.

Strategy:
- Read the corrupted file as text.
- Find top-level entries of the form "<key>": { ... } by locating the opening brace
  and scanning forward with a simple state machine that tracks string quoting and
  brace depth to find the matching closing brace.
- Parse each recovered JSON object individually.
- Load the backup documents_db.json.bak (if present) and merge recovered entries
  into it (recovered entries override the backup for the same keys).
- Write a recovered file documents_db.json.recovered_<timestamp>.json next to the original.

This script is conservative: it does not overwrite the original documents_db.json.
It prints a short summary of recovered keys and counts.
"""
import json
import re
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path(__file__).parent
DB_PATH = ROOT / 'documents_db.json'
BAK_PATH = ROOT / 'documents_db.json.bak'


def find_top_level_entries(text: str):
    """Yield tuples (key, json_text, start_idx, end_idx) for top-level object entries.
    We look for pattern: "<key>": { ...matching braces... }
    The scanner respects string quoting to avoid counting braces inside strings.
    """
    pattern = re.compile(r'"([0-9a-fA-F\-]{8,36})"\s*:\s*{')
    for m in pattern.finditer(text):
        key = m.group(1)
        brace_start = m.end() - 1  # index of the '{'
        i = brace_start
        depth = 0
        in_str = False
        esc = False
        end_idx = None
        while i < len(text):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            i += 1
        if end_idx is not None:
            json_text = text[brace_start:end_idx+1]
            yield key, json_text, m.start(), end_idx+1
        else:
            # incomplete entry; skip
            continue


def main():
    if not DB_PATH.exists():
        print(f"No documents_db.json at {DB_PATH}")
        return 1

    txt = DB_PATH.read_text(encoding='utf-8', errors='replace')
    recovered = {}
    recovered_order = []
    for key, jtext, s, e in find_top_level_entries(txt):
        try:
            obj = json.loads(jtext)
            recovered[key] = obj
            recovered_order.append(key)
        except Exception as ex:
            # skip entries that don't parse cleanly
            print(f"Skipping key {key}: json.loads failed: {ex}")

    print(f"Found {len(recovered)} complete top-level entries in the corrupted file")

    # Load backup if present
    base = {}
    if BAK_PATH.exists():
        try:
            base = json.loads(BAK_PATH.read_text(encoding='utf-8'))
            print(f"Loaded backup with {len(base)} entries from {BAK_PATH.name}")
        except Exception as ex:
            print(f"Failed to load backup {BAK_PATH}: {ex}")
            base = {}
    else:
        print("No backup file found; starting from empty DB")

    # Apply recovered entries into base (override where key exists)
    merged = dict(base)
    for k in recovered_order:
        merged[k] = recovered[k]

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = DB_PATH.with_name(f'documents_db.json.recovered_{ts}.json')
    try:
        out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Wrote recovered DB to {out_path}")
        print(f"Recovered {len(recovered)} entries; merged DB now has {len(merged)} entries")
    except Exception as ex:
        print(f"Failed to write recovered DB: {ex}")
        return 2

    # Show a short sample of recovered keys
    if recovered_order:
        print("Recovered keys (first 20):")
        for k in recovered_order[:20]:
            print(" -", k)

    print('\nDone.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
