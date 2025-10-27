import json
from pathlib import Path
ROOT = Path(__file__).parent.parent
p = ROOT.joinpath('backend', 'api', 'documents_db.json')
allrec = json.loads(p.read_text(encoding='utf-8'))
key='4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = allrec.get(key)
if not rec:
    print('doc not found')
else:
    print('status', rec.get('status'))
    print('raw_extracted present', bool(rec.get('raw_extracted')))
    print('extracted_data present', bool(rec.get('extracted_data')))
    print('extracted_data items:', rec.get('extracted_data', {}).get('itens'))
    print('aggregates', rec.get('aggregates'))
    print('\n--- raw_extracted snippet ---\n')
    re = rec.get('raw_extracted') or ''
    print(re[:800])
