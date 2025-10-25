import requests

PDF_PATH = r'c:\labz\fiscal-extraction-system-COMPLETO\nota_exemplo.pdf'
API_URL = 'http://localhost:8000/api/v1/documents/upload'

with open(PDF_PATH, 'rb') as f:
    files = {'files': f}
    response = requests.post(API_URL, files=files)
    print('Status:', response.status_code)
    print('Response:', response.text)
