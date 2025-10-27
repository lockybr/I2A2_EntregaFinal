import json
from pathlib import Path
ROOT = Path(__file__).parent.parent
p = ROOT.joinpath('backend', 'api', 'documents_db.json')
allrec = json.loads(p.read_text(encoding='utf-8'))
key='4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = allrec[key]
raw = rec.get('raw_extracted') or ''
# extract json like main._extract_json_text
import re
m = re.search(r'```json\s*(\{.*?\})\s*```', raw, flags=re.DOTALL)
if m:
    ct = m.group(1)
else:
    m2 = re.search(r'```\s*(\{.*?\})\s*```', raw, flags=re.DOTALL)
    if m2:
        ct = m2.group(1)
    else:
        first = raw.find('{')
        last = raw.rfind('}')
        ct = raw[first:last+1] if first!=-1 and last!=-1 and last>first else None

print('candidate length', len(ct) if ct else None)
parsed = json.loads(ct)
print('parsed item:', parsed.get('itens')[0])

# import normalize_extracted
from backend.api.main import normalize_extracted
norm = normalize_extracted(parsed)
print('normalized item:', norm.get('itens')[0])
