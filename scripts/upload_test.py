import requests
import os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
file_path = os.path.join(REPO_ROOT, 'frontend', 'upload_test2.txt')
with open(file_path, 'wb') as f:
    f.write(b'Teste UI upload 2')
with open(file_path, 'rb') as f:
    r = requests.post('http://127.0.0.1:8000/api/v1/documents/upload', files={'files': ('upload_test2.txt', f)})
    print(r.status_code)
    print(r.text)
