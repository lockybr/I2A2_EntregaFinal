import os
import shutil
import tempfile
import uuid
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAMPLE = os.path.join(ROOT, 'assets', 'nota_exemplo.pdf')
if not os.path.exists(SAMPLE):
    print('Sample not found:', SAMPLE)
    raise SystemExit(1)

# prepare env
import sys
sys.path.insert(0, ROOT)

# import persistence and process_document
from backend.api import persistence
from backend.api import main

# create a doc entry
doc_id = str(uuid.uuid4())
filename = os.path.basename(SAMPLE)

tmp_dir = tempfile.gettempdir()
tmp_path = os.path.join(tmp_dir, f"{doc_id}_{filename}")
shutil.copyfile(SAMPLE, tmp_path)

persistence.documents_db[doc_id] = {
    "id": doc_id,
    "filename": filename,
    "uploaded_at": datetime.now().isoformat(),
    "status": "ingestao",
    "progress": 5,
    "ocr_text": None,
    "raw_file": None,
    "tmp_path": tmp_path,
    "raw_extracted": None,
    "extracted_data": None
}

persistence.save_documents_db()

print('Starting processing for', doc_id)
main.process_document(doc_id, tmp_path, filename)

print('Done. Document record:')
import json
print(json.dumps(persistence.documents_db.get(doc_id, {}), indent=2, ensure_ascii=False))
