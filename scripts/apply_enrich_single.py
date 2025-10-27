import json
from pathlib import Path
ROOT = Path(__file__).parent.parent
DB = ROOT.joinpath('backend','api','documents_db.json')
allrec = json.loads(DB.read_text(encoding='utf-8'))
key='4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = allrec.get(key)
if not rec:
    print('doc not found')
    raise SystemExit(1)
print('running enrichment for', key)
import importlib.util
import importlib.machinery
import sys
sys.path.insert(0, str(ROOT))
# Load enrichment_agent directly from file to avoid importing package __init__ that pulls heavy deps
ea_path = ROOT.joinpath('backend', 'agents', 'enrichment_agent.py')
spec = importlib.util.spec_from_file_location('enrichment_agent', str(ea_path))
if spec is None or spec.loader is None:
    raise RuntimeError(f'Failed to load spec for {ea_path}')
enrichment_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enrichment_agent)
new_extracted, info = enrichment_agent.enrich_record(rec)
allrec[key]['extracted_data'] = new_extracted
allrec[key]['aggregates'] = info.get('aggregates')
DB.write_text(json.dumps(allrec, ensure_ascii=False, indent=2), encoding='utf-8')
print('done. aggregates:', info.get('aggregates'))
print('new item:', new_extracted.get('itens')[0] if new_extracted.get('itens') else None)
