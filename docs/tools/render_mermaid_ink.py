import base64
import urllib.request
import sys
from pathlib import Path

in_path = Path(__file__).parent / '..' / 'assets' / 'architecture_sanitized.mmd'
out_path = Path(__file__).parent / '..' / 'assets' / 'architecture.png'

in_path = in_path.resolve()
out_path = out_path.resolve()

if not in_path.exists():
    print(f"Input file not found: {in_path}")
    sys.exit(2)

code = in_path.read_text(encoding='utf-8')
# base64 urlsafe, remove padding
b64 = base64.urlsafe_b64encode(code.encode('utf-8')).decode('ascii').rstrip('=')
url = f'https://mermaid.ink/img/{b64}'
print(f"Fetching from: {url}")

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'mermaid-fetcher/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            print(f"Failed to fetch image, status: {resp.status}")
            sys.exit(3)
        data = resp.read()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
    print(f"Saved PNG to: {out_path}")
except Exception as e:
    print(f"Error fetching PNG: {e}")
    sys.exit(4)
