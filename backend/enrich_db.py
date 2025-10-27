"""CLI script to run the enrichment agent over the persisted documents DB.

Usage: python backend/enrich_db.py

It will load backend/api/documents_db.json, apply enrichment heuristics to each record
that appears to have missing fields, update extracted_data and aggregates, and write the DB back.
"""
import os
import json
from backend.agents import enrichment_agent


DB_PATH = os.path.join(os.path.dirname(__file__), 'api', 'documents_db.json')


def load_db(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_db(path, db):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def needs_enrichment(rec):
    ex = rec.get('extracted_data')
    if not ex:
        return True
    # naive check: any top-level required fields missing or null
    required = ['emitente', 'destinatario', 'valor_total', 'data_emissao']
    for k in required:
        v = ex.get(k)
        if v is None:
            return True
    return False


def main():
    db = load_db(DB_PATH)
    if not db:
        print(f"No documents found at {DB_PATH}")
        return

    updated = 0
    for k, rec in list(db.items()):
        try:
            if not needs_enrichment(rec):
                continue
            new_extracted, info = enrichment_agent.enrich_record(rec)
            rec['extracted_data'] = new_extracted
            rec['aggregates'] = info.get('aggregates')
            db[k] = rec
            updated += 1
            print(f"Enriched {k}: filled {list(info.get('report', {}).get('filled', {}).keys())}")
        except Exception as e:
            print(f"Failed to enrich {k}: {e}")

    if updated:
        save_db(DB_PATH, db)
        print(f"Updated {updated} documents and saved to {DB_PATH}")
    else:
        print("No documents needed enrichment")


if __name__ == '__main__':
    main()
