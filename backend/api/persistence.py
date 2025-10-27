import os
import json
import threading
import tempfile
import shutil
import sys
from datetime import datetime

# Path to the JSON DB file. Allow override via DOCUMENTS_DB_PATH env var for safe testing and recovery.
DATA_STORE_PATH = os.environ.get('DOCUMENTS_DB_PATH') or os.path.join(os.path.dirname(__file__), 'documents_db.json')

# In-memory store and lock
documents_db = {}
_db_lock = threading.Lock()


def load_documents_db():
    global documents_db
    try:
        if os.path.exists(DATA_STORE_PATH):
            try:
                with open(DATA_STORE_PATH, 'r', encoding='utf-8') as f:
                    documents_db = json.load(f)
            except Exception as e_load:
                # Move corrupted DB aside and attempt to recover from backup if present
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                corrupt_path = DATA_STORE_PATH + f'.corrupt_{ts}'
                try:
                    shutil.move(DATA_STORE_PATH, corrupt_path)
                    print(f"[PERSIST] documents_db.json was corrupted; moved to {corrupt_path}", file=sys.stderr)
                except Exception as e_mv:
                    print(f"[PERSIST] failed to move corrupted DB: {e_mv}", file=sys.stderr)
                # try backup next to original
                bak = DATA_STORE_PATH + '.bak'
                if os.path.exists(bak):
                    try:
                        with open(bak, 'r', encoding='utf-8') as f2:
                            documents_db = json.load(f2)
                        # write recovered backup back to main path atomically
                        save_documents_db()
                        print(f"[PERSIST] recovered documents_db from backup {bak}", file=sys.stderr)
                        return
                    except Exception as e_bak:
                        print(f"[PERSIST] backup read failed: {e_bak}", file=sys.stderr)
                documents_db = {}
        else:
            documents_db = {}
    except Exception as e:
        print(f"[PERSIST] failed to load documents_db: {e}", file=sys.stderr)
        documents_db = {}


def save_documents_db():
    try:
        with _db_lock:
            dirpath = os.path.dirname(DATA_STORE_PATH)
            fd, tmp = tempfile.mkstemp(prefix='documents_db_', suffix='.tmp', dir=dirpath)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(documents_db, f, ensure_ascii=False, indent=2)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        # not critical on some platforms
                        pass
                # Make a rotated backup of the previous DB (best-effort)
                try:
                    if os.path.exists(DATA_STORE_PATH):
                        bak = DATA_STORE_PATH + '.bak'
                        shutil.copy2(DATA_STORE_PATH, bak)
                except Exception as e_bak:
                    print(f"[PERSIST] warning: failed to write backup: {e_bak}", file=sys.stderr)
                # replace atomically
                os.replace(tmp, DATA_STORE_PATH)
            finally:
                # cleanup temp if still exists
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
    except Exception as e:
        print(f"[PERSIST] failed to save documents_db: {e}", file=sys.stderr)


if __name__ == '__main__':
    # quick smoke test
    load_documents_db()
    print('Loaded', len(documents_db), 'records')
