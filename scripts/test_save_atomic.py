import importlib
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from backend.api import persistence
print('Loaded persistence module')
# make a tiny change and save
key = '__test_atomic_key__'
orig = persistence.documents_db.get(key)
persistence.documents_db[key] = {'id': key, 'filename': 'test', 'uploaded_at': 'now', 'status': 'test', 'progress': 0}
persistence.save_documents_db()
print('Saved DB with test key')
# reload file content to ensure key present
import json
with open(str(ROOT.joinpath('backend','api','documents_db.json')), 'r', encoding='utf-8') as f:
    j = json.load(f)
print('test key in file?', key in j)
# restore previous state
if orig is None:
    j.pop(key, None)
else:
    j[key] = orig
with open(str(ROOT.joinpath('backend','api','documents_db.json')), 'w', encoding='utf-8') as f:
    json.dump(j, f, ensure_ascii=False, indent=2)
print('Restored DB original state')
