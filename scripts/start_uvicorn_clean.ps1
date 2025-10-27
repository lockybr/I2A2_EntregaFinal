$env:DOCUMENTS_DB_PATH = 'C:\labz\fiscal-extraction-system-COMPLETO\backend\api\documents_db.clean.json'
& 'C:\labz\fiscal-extraction-system-COMPLETO\.venv\Scripts\python.exe' -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
