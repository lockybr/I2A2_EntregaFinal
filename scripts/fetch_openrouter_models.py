import os, requests, json
key = os.environ.get('OPENROUTER_API_KEY')
headers = {"Authorization": f"Bearer {key}"} if key else {}
urls = [
    "https://openrouter.ai/api/v1/models?max_price=0&order=top-weekly",
    "https://api.openrouter.ai/v1/models?max_price=0&order=top-weekly",
]
for u in urls:
    try:
        print('\nRequesting:', u)
        r = requests.get(u, headers=headers, timeout=10)
        print('status', r.status_code)
        txt = r.text
        try:
            data = r.json()
        except Exception:
            print('not json:', txt[:400])
            continue
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('models') or data.get('data') or data.get('results') or []
        ids = []
        for m in items:
            if isinstance(m, dict):
                mid = m.get('id') or m.get('model') or m.get('name')
            else:
                mid = str(m)
            if mid:
                ids.append(mid)
        print('found', len(ids), 'models; sample:', ids[:20])
    except Exception as e:
        print('failed', e)
