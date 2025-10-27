import json
from pathlib import Path
p = Path(__file__).parent / 'documents_db.json'
if not p.exists():
    print('no db')
    raise SystemExit(1)

j = json.loads(p.read_text(encoding='utf-8'))
key = '4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = j.get(key)
if not rec:
    print('not found')
    raise SystemExit(2)

print('raw_extracted:')
print(rec.get('raw_extracted'))
print('\nextracted_data:')
import pprint
pprint.pprint(rec.get('extracted_data'))
print('\nocr_text (first 400 chars):')
print((rec.get('ocr_text') or '')[:400])
