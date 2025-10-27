import json, re
from pathlib import Path
ROOT = Path(__file__).parent.parent
p = ROOT.joinpath('backend', 'api', 'documents_db.json')
j = json.loads(p.read_text(encoding='utf-8'))
key='4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = j[key]
raw = rec.get('raw_extracted') or ''
print('raw length', len(raw))

def extract(s):
    m = re.search(r'```json\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'```\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
    if m2:
        return m2.group(1).strip()
    first = s.find('{')
    last = s.rfind('}')
    if first!=-1 and last!=-1 and last>first:
        return s[first:last+1]
    return None

ct = extract(raw)
print('candidate_text startswith:', ct.strip()[:80])
try:
    parsed = json.loads(ct)
    print('parsed keys:', list(parsed.keys()))
    print('first item:', parsed.get('itens')[0])
except Exception as e:
    print('parse error', e)
    # show snippet
    print(ct[:400])
