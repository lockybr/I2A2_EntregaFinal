import requests
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PDF_PATH = os.path.join(REPO_ROOT, 'assets', 'nota_exemplo.pdf')
API_URL = 'http://127.0.0.1:8000/api/v1/documents/upload'

if not os.path.exists(PDF_PATH):
    print('Sample PDF not found at', PDF_PATH)
    raise SystemExit(1)

with open(PDF_PATH, 'rb') as f:
    files = [('files', (os.path.basename(PDF_PATH), f, 'application/pdf'))]
    try:
        r = requests.post(API_URL, files=files, timeout=30)
        print('Status:', r.status_code)
        print('Response:', r.text)
    except Exception as e:
        print('Upload failed:', e)
