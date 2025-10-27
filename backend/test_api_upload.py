import requests
import os

# use repo-relative assets path for sample PDF
HERE = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PDF_PATH = os.path.join(REPO_ROOT, 'assets', 'nota_exemplo.pdf')
API_URL = 'http://localhost:8000/api/v1/documents/upload'

with open(PDF_PATH, 'rb') as f:
    files = {'files': f}
    response = requests.post(API_URL, files=files)
    print('Status:', response.status_code)
    print('Response:', response.text)
