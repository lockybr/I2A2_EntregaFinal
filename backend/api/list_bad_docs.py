import json
from pathlib import Path
p = Path(__file__).parent / 'documents_db.json'
if not p.exists():
    print('documents_db.json not found')
    raise SystemExit(1)

d = json.loads(p.read_text(encoding='utf-8'))
bad = []
for k, v in d.items():
    re = v.get('raw_extracted')
    ee = v.get('extracted_error')
    ed = v.get('extracted_data')
    if isinstance(re, str) and 'User not found' in re:
        bad.append((k, 'raw_extracted', re))
        continue
    if isinstance(ee, str) and 'User not found' in ee:
        bad.append((k, 'extracted_error', ee))
        continue
    # sometimes extracted_data may contain an error string
    if isinstance(ed, str) and 'User not found' in ed:
        bad.append((k, 'extracted_data', ed))
        continue

print(json.dumps({'count': len(bad), 'items': bad}, ensure_ascii=False, indent=2))
