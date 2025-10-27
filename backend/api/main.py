# ...existing code...
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import json
import uvicorn
import uuid
from datetime import datetime
import pytesseract
import pdf2image
import os
import threading
import sys
import tempfile
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import requests
import shutil
import time
# Read OpenRouter API key from environment for safety. If not present, LLM calls will be attempted
# but may fail. Avoid hardcoding secrets in source.
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_KEY') or None
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3.1:free"
if not OPENROUTER_API_KEY:
    print('[CONFIG] Warning: OPENROUTER_API_KEY not set. LLM calls may fail.', file=sys.stderr)
else:
    print('[CONFIG] OPENROUTER_API_KEY loaded from environment', file=sys.stderr)


def _mask_key(k: str) -> str:
    try:
        if not k:
            return '<not-set>'
        s = str(k)
        if len(s) <= 10:
            return s[0:3] + '...' + s[-3:]
        return s[:6] + '...' + s[-6:]
    except Exception:
        return '<error>'


# Cache/utility to fetch free models from OpenRouter dynamically
_FREE_MODELS_CACHE = []
def get_openrouter_free_models(limit: int = 20):
    """Return a list of free model identifiers from OpenRouter (cached).
    Tries a couple of hostnames and falls back to a small default list.
    """
    global _FREE_MODELS_CACHE
    if _FREE_MODELS_CACHE:
        return _FREE_MODELS_CACHE[:limit]
    if not OPENROUTER_API_KEY:
        return [OPENROUTER_MODEL, 'minimax/minimax-m2:free']
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    urls = [
        "https://openrouter.ai/api/v1/models?max_price=0&order=top-weekly",
        "https://api.openrouter.ai/v1/models?max_price=0&order=top-weekly",
    ]
    models = []
    for u in urls:
        try:
            r = requests.get(u, headers=headers, timeout=8)
            if r.status_code != 200:
                continue
            data = r.json()
            # data might be list or dict with a 'models' key
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('models') or data.get('data') or data.get('results') or []
            for m in items:
                try:
                    if isinstance(m, dict):
                        mid = m.get('id') or m.get('model') or m.get('name')
                    else:
                        mid = str(m)
                    if mid and mid not in models:
                        models.append(mid)
                except Exception:
                    continue
            if models:
                _FREE_MODELS_CACHE = models
                return models[:limit]
        except Exception:
            continue
    # curated fallback list (kept as last-resort). If dynamic fetch succeeds we update _FREE_MODELS_CACHE at startup.
    HARDCODED_FALLBACK_MODELS = [
        'deepseek/deepseek-chat-v3.1:free',
        'minimax/minimax-m2:free',
        'deepseek/deepseek-chat-v3.0:free',
        'minimax/minimax-m1:free',
        'mosaicml/mpt-7b-instruct:free',
        'stabilityai/stablelm-tuned-alpha-3b:free',
        'anthropic/claude-instant-1:free',
        'tiiuae/falcon-7b:free',
        'eleutherai/gpt-j-6b:free',
        'cerebras/Cerebras-GPT-2.7B:free',
        'OpenAssistant/oasst-sft-6-llama-30b:free',
        'openai/gpt-4o-mini:free'
    ]
    # ensure we include configured model at the front (if not already present)
    result = []
    if OPENROUTER_MODEL:
        result.append(OPENROUTER_MODEL)
    for m in (models or []):
        if m and m not in result:
            result.append(m)
    for m in HARDCODED_FALLBACK_MODELS:
        if m not in result:
            result.append(m)
    _FREE_MODELS_CACHE = result
    return result[:limit]


# Global in-memory rotation list (populated at startup). Will contain up to 50 model ids ordered by best weekly.
OPENROUTER_FREE_MODELS = []

def initialize_openrouter_free_models(at_most: int = 50):
    """Fetch the top weekly free models from OpenRouter and populate OPENROUTER_FREE_MODELS (ordered).
    On failure, fall back to the cached/hardcoded list.
    This is intended to run at server startup once.
    """
    global OPENROUTER_FREE_MODELS, _FREE_MODELS_CACHE
    try:
        models = get_openrouter_free_models(limit=at_most)
        if models:
            OPENROUTER_FREE_MODELS = models[:at_most]
            # ensure cache reflects this prioritized order
            _FREE_MODELS_CACHE = list(OPENROUTER_FREE_MODELS)
            print(f"[LLM] Loaded {len(OPENROUTER_FREE_MODELS)} free models for rotation", file=sys.stderr)
            return
    except Exception as e:
        print(f"[LLM] failed to initialize model list dynamically: {e}", file=sys.stderr)
    # fallback: use whatever is already in cache or hardcoded
    fallback = _FREE_MODELS_CACHE or get_openrouter_free_models(limit=at_most)
    OPENROUTER_FREE_MODELS = fallback[:at_most]
    print(f"[LLM] Using fallback model list with {len(OPENROUTER_FREE_MODELS)} entries", file=sys.stderr)

# Print masked key at startup so it's easy to verify which key this process is using
try:
    masked = _mask_key(os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_KEY'))
    print(f"[CONFIG] OPENROUTER_API_KEY (masked) = {masked}", file=sys.stderr)
except Exception:
    pass


# Inicializa o FastAPI antes de usar decorators e middlewares
app = FastAPI(
    title="Sistema de Extração Fiscal API",
    description="API para extração automatizada de dados fiscais com agentes de IA",
    version="1.0.0"
)

# CORS deve ser o primeiro middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Tesseract executable path.
# Priority: 1) TESSERACT_CMD env var, 2) project-local tools/tesseract (useful for Windows portable),
# 3) system PATH (shutil.which)
import shutil
TESSERACT_CMD = os.environ.get('TESSERACT_CMD')
if not TESSERACT_CMD:
    # project-local candidate (repo relative)
    repo_tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools', 'tesseract'))
    if os.name == 'nt':
        candidate = os.path.join(repo_tools_path, 'tesseract.exe')
    else:
        candidate = os.path.join(repo_tools_path, 'tesseract')
    if os.path.exists(candidate):
        TESSERACT_CMD = candidate
    else:
        # fallback to system tesseract in PATH
        TESSERACT_CMD = shutil.which('tesseract')

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    print(f"[CONFIG] Using tesseract executable: {TESSERACT_CMD}", file=sys.stderr)
else:
    # leave pytesseract default; OCR calls will fail later if not available
    print('[CONFIG] Warning: tesseract executable not found. OCR will fail unless available in PATH or TESSERACT_CMD is set.', file=sys.stderr)

# Configure Poppler path (used by pdf2image on Windows). Allow override via env var POPPLER_PATH.
try:
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
except Exception:
    REPO_ROOT = os.getcwd()

DEFAULT_POPPLER = os.path.join(REPO_ROOT, 'poppler', 'Library', 'bin')
POPPLER_PATH = os.environ.get('POPPLER_PATH') or (DEFAULT_POPPLER if os.path.exists(DEFAULT_POPPLER) else None)
if POPPLER_PATH:
    print(f"[CONFIG] Using poppler path: {POPPLER_PATH}", file=sys.stderr)
else:
    print('[CONFIG] No poppler path found in repo; pdf2image will rely on system poppler or may fail on Windows. Set POPPLER_PATH env var to override.', file=sys.stderr)

# Persistence moved to backend.api.persistence to allow lightweight imports for tests
try:
    # when running as package (uvicorn api.main:app)
    from . import persistence
except Exception:
    # fallback when running as module from backend folder (uvicorn main:app)
    from backend.api import persistence
DATA_STORE_PATH = persistence.DATA_STORE_PATH
documents_db = persistence.documents_db
_db_lock = persistence._db_lock
load_documents_db = persistence.load_documents_db
save_documents_db = persistence.save_documents_db

# Load persisted DB at startup
load_documents_db()
# rebind the local reference to the persistence module's store (persistence.load_documents_db may replace the object)
try:
    documents_db = persistence.documents_db
except Exception:
    pass
# Global flag indicating whether chat/completions is allowed with current key
LLM_AVAILABLE = None


@app.on_event("startup")
def _check_llm_available():
    """Perform a lightweight check to see if the configured OPENROUTER_API_KEY can call chat/completions.
    This prevents attempting LLM calls that will return 401 for every document and lets us
    fall back to heuristics immediately.
    """
    global LLM_AVAILABLE
    key = OPENROUTER_API_KEY
    if not key:
        LLM_AVAILABLE = False
        print('[LLM-CHK] OPENROUTER_API_KEY not set; skipping LLM usage', file=sys.stderr)
        # still populate free-models fallback for local offline operation
        try:
            initialize_openrouter_free_models(at_most=50)
        except Exception:
            pass
        return

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    test_body = {
        "model": "minimax/minimax-m2:free",
        "messages": [{"role": "user", "content": "hi"}]
    }

    # Try a couple of known OpenRouter endpoints before deciding
    endpoints = [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://api.openrouter.ai/v1/chat/completions",
    ]
    errors = []
    try:
        for u in endpoints:
            try:
                r = requests.post(u, json=test_body, headers=headers, timeout=8)
            except Exception as e:
                errors.append(f"{u} - request error: {e}")
                continue

            if r.status_code == 200:
                LLM_AVAILABLE = True
                print('[LLM-CHK] OpenRouter chat/completions reachable with current key', file=sys.stderr)
                return
            # Auth failures are actionable: stop and report succinctly
            if r.status_code == 401:
                LLM_AVAILABLE = False
                print(f"[LLM-CHK] OpenRouter auth failed (401). Masked key={_mask_key(key)}", file=sys.stderr)
                return
            # Non-200 responses: log concise info (avoid dumping full provider metadata)
            txt = (r.text or '')
            one_line = ' '.join(txt.splitlines())[:300]
            errors.append(f"{u} - status {r.status_code}: {one_line}")

        # If we get here, none of the endpoints returned 200
        LLM_AVAILABLE = False
        # Print a short summary of the attempts (not the full responses)
        try:
            print('[LLM-CHK] OpenRouter chat/completions probe failed. Attempts:', file=sys.stderr)
            for e in errors[:5]:
                print(f"[LLM-CHK]  - {e}", file=sys.stderr)
        except Exception:
            pass
        # populate free-models fallback so processing can continue using local rotation
        try:
            initialize_openrouter_free_models(at_most=50)
        except Exception as ie:
            print(f"[LLM-CHK] failed initializing free-models list: {ie}", file=sys.stderr)
        return
    except Exception as e:
        LLM_AVAILABLE = False
        print(f"[LLM-CHK] OpenRouter chat/completions test unexpected error: {e}", file=sys.stderr)
        try:
            initialize_openrouter_free_models(at_most=50)
        except Exception as ie:
            print(f"[LLM-CHK] failed initializing free-models list: {ie}", file=sys.stderr)
        return
pipeline_steps = [
    {"step": 1, "name": "ingestao"},
    {"step": 2, "name": "preprocessamento"},
    {"step": 3, "name": "ocr"},
    {"step": 4, "name": "nlp"},
    {"step": 5, "name": "validacao"},
    {"step": 6, "name": "finalizado"}
]


@app.get("/")
async def root():
    return {
        "message": "Sistema de Extração Fiscal API v1.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/debug/llm_test")
async def llm_test():
    """Quick diagnostic endpoint to verify the OpenRouter API key and base URLs from the running process.
    Returns masked key and attempts simple GET requests to likely OpenRouter model endpoints.
    """
    key = OPENROUTER_API_KEY
    masked = _mask_key(key)
    results = []
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    urls = ["https://openrouter.ai/api/v1/models", "https://api.openrouter.ai/v1/models"]
    try:
        import requests
        for u in urls:
            try:
                r = requests.get(u, headers=headers, timeout=10)
                # keep response short for safety
                txt = r.text
                results.append({"url": u, "status_code": r.status_code, "text": txt[:1500]})
            except Exception as e:
                results.append({"url": u, "error": str(e)})
    except Exception as e:
        # requests not available or failed to import
        results.append({"error": f"requests import failed: {e}"})

    return {"masked_key": masked, "results": results}


def all_nulls(x):
    if x is None:
        return True
    if isinstance(x, dict):
        return all(all_nulls(v) for v in x.values())
    if isinstance(x, list):
        return all(all_nulls(i) for i in x)
    return False


def simple_receipt_parser(text: Optional[str]):
    """Heuristic parser for simple receipts: extracts total, possible company name and item lines."""
    import re
    out = {
        "emitente": {"razao_social": None, "cnpj": None, "inscricao_estadual": None, "endereco": None},
        "destinatario": {"razao_social": None, "cnpj": None, "inscricao_estadual": None, "endereco": None},
        "itens": [],
        "impostos": {"icms": {"aliquota": None, "base_calculo": None, "valor": None}, "ipi": {"valor": None}, "pis": {"valor": None}, "cofins": {"valor": None}},
        "codigos_fiscais": {"cfop": None, "cst": None, "ncm": None, "csosn": None},
        "numero_nota": None, "chave_acesso": None, "data_emissao": None, "natureza_operacao": None, "forma_pagamento": None, "valor_total": None
    }
    if not text:
        return out
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Heuristic: first non-empty line likely company name
    if lines:
        out['emitente']['razao_social'] = lines[0]

    # find currency-like values, prefer lines with 'TOTAL' or 'TOTAL:'
    total_re = re.compile(r'(?:total|valor total|valor|total\s*[:\-])\s*[:\-]?\s*R?\$?\s*([0-9]+[\.,][0-9]{2})', re.IGNORECASE)
    any_money_re = re.compile(r'R?\$\s*([0-9]+[\.,][0-9]{2})')
    for ln in reversed(lines[-10:]):
        m = total_re.search(ln)
        if m:
            out['valor_total'] = m.group(1).replace(',', '.')
            break
    if out['valor_total'] is None:
        # fallback: last currency-like value in the doc
        for ln in reversed(lines):
            m2 = any_money_re.search(ln)
            if m2:
                out['valor_total'] = m2.group(1).replace(',', '.')
                break

    # Attempt to extract simple item: look for lines with a description followed by a number or currency
    item_line_re = re.compile(r'^(.{3,60})\s+(\d+)\s+R?\$?\s*([0-9]+[\.,][0-9]{2})$')
    for ln in lines:
        m = item_line_re.match(ln)
        if m:
            desc = m.group(1).strip()
            qty = m.group(2)
            val = m.group(3).replace(',', '.')
            out['itens'].append({"descricao": desc, "quantidade": qty, "unidade": None, "valor_unitario": val, "valor_total": val})
    # If no items matched, try pairing a line with following line that contains a currency
    if not out['itens']:
        for i, ln in enumerate(lines[:-1]):
            if any_money_re.search(lines[i+1]):
                amt = any_money_re.search(lines[i+1]).group(1).replace(',', '.')
                out['itens'].append({"descricao": ln, "quantidade": None, "unidade": None, "valor_unitario": amt, "valor_total": amt})
                break

    return out


def merge_dicts(dst, src):
    if not isinstance(dst, dict) or not isinstance(src, dict):
        return dst
    for k, v in src.items():
        if k not in dst or dst[k] is None:
            dst[k] = v
        else:
            if isinstance(v, dict):
                merge_dicts(dst[k], v)
            elif isinstance(v, list) and not dst[k]:
                dst[k] = v
    return dst


def normalize_extracted(extracted):
    """Normalize extracted JSON into canonical schema and types.
    - move fields from 'outros' into top-level if present
    - normalize CNPJ (digits only)
    - normalize dates to ISO YYYY-MM-DD when possible
    - normalize numeric strings to floats
    - ensure itens is an array of normalized items
    """
    import re
    if not extracted or not isinstance(extracted, dict):
        return extracted

    out = {}

    # helpers
    def only_digits(s):
        if not s: return None
        return re.sub(r'\D', '', str(s)) or None

    def is_garbage_str(s):
        if s is None: return True
        try:
            ss = str(s).strip()
        except Exception:
            return True
        if not ss: return True
        # short tokens are likely not useful
        if len(ss) <= 3:
            return True
        low = ss.lower()
        # common boilerplate / noise seen in OCR/LLM outputs
        garbage_tokens = ['recebe', 'visualize', 'boleto', 'nf-e', 'nfe', 'nf-e', 'nf e', 'visualizar', 'venda mercadoria']
        for t in garbage_tokens:
            if t in low:
                return True
        return False

    def parse_number(s):
        if s is None: return None
        if isinstance(s, (int, float)): return float(s)
        try:
            ss = str(s).strip()
            # keep only digits and separators
            ss = re.sub(r"[^0-9\.,-]", "", ss)
            # If contains both '.' and ',', assume '.' is thousand sep and ',' is decimal
            if '.' in ss and ',' in ss:
                ss = ss.replace('.', '').replace(',', '.')
            elif ',' in ss:
                # only comma -> decimal separator
                ss = ss.replace('.', '').replace(',', '.')
            elif '.' in ss:
                # only dot present: decide if it's decimal or thousand separator
                parts = ss.split('.')
                if len(parts) == 2 and len(parts[1]) == 2:
                    # looks like decimal with two digits
                    ss = ss
                else:
                    # treat dots as thousand separators
                    ss = ss.replace('.', '')
            if ss in ['', '-', ',', '.']:
                return None
            return float(ss)
        except Exception:
            return None

    def parse_date(s):
        if not s: return None
        s = str(s).strip()
        # dd/mm/yyyy
        m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
        if m:
            d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            return d
        # try ISO
        m2 = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m2:
            return s
        return None

    # start with a copy to avoid mutating original
    src = dict(extracted)

    # If there's an 'outros' block, lift some fields
    outros = src.pop('outros', {}) if isinstance(src.get('outros', {}), dict) else {}
    for k in ['numero_nota', 'chave_acesso', 'data_emissao', 'natureza_operacao', 'forma_pagamento', 'valor_total']:
        if k in src and src[k] is not None:
            out[k] = src[k]
        elif k in outros and outros[k] is not None:
            out[k] = outros[k]
        else:
            out[k] = src.get(k) if k in src else None

    # emitente/destinatario
    def normalize_party(p):
        if not p or not isinstance(p, dict): return {"razao_social": None, "cnpj": None, "inscricao_estadual": None, "endereco": None}
        rs = p.get('razao_social') or p.get('nome') or p.get('razao') or None
        if is_garbage_str(rs):
            rs = None
        cnpj_raw = p.get('cnpj') or p.get('cpf') or p.get('cnpj_emitente')
        cnpj = only_digits(cnpj_raw)
        ie_raw = p.get('inscricao_estadual') or p.get('inscricao') or p.get('ie')
        ie = only_digits(ie_raw)
        endereco = p.get('endereco') or p.get('logradouro') or None
        if endereco and is_garbage_str(endereco):
            endereco = None
        return {
            "razao_social": rs,
            "cnpj": cnpj,
            "inscricao_estadual": ie,
            "endereco": endereco
        }

    out['emitente'] = normalize_party(src.get('emitente') or {})
    out['destinatario'] = normalize_party(src.get('destinatario') or {})

    # impostos
    imp = src.get('impostos') or {}
    out['impostos'] = {
        'icms': {
            'aliquota': parse_number(imp.get('icms', {}).get('aliquota') if isinstance(imp.get('icms'), dict) else None),
            'base_calculo': parse_number(imp.get('icms', {}).get('base_calculo') if isinstance(imp.get('icms'), dict) else None),
            'valor': parse_number(imp.get('icms', {}).get('valor') if isinstance(imp.get('icms'), dict) else None),
        },
        'ipi': {'valor': parse_number((imp.get('ipi') or {}).get('valor') if isinstance(imp.get('ipi'), dict) else None)},
        'pis': {'valor': parse_number((imp.get('pis') or {}).get('valor') if isinstance(imp.get('pis'), dict) else None)},
        'cofins': {'valor': parse_number((imp.get('cofins') or {}).get('valor') if isinstance(imp.get('cofins'), dict) else None)},
    }

    # codigos fiscais
    cf = src.get('codigos_fiscais') or {}
    out['codigos_fiscais'] = {
        'cfop': cf.get('cfop') or src.get('cfop') or None,
        'cst': cf.get('cst') or src.get('cst') or None,
        'ncm': cf.get('ncm') or src.get('ncm') or None,
        'csosn': cf.get('csosn') or src.get('csosn') or None,
    }

    # itens
    items = []
    raw_items = src.get('itens') or []
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict): continue
            desc = it.get('descricao') or it.get('desc') or None
            if is_garbage_str(desc):
                desc = None
            items.append({
                'descricao': desc,
                'quantidade': parse_number(it.get('quantidade')),
                'unidade': it.get('unidade') or it.get('un') or None,
                'valor_unitario': parse_number(it.get('valor_unitario') or it.get('valor') or it.get('preco')),
                'valor_total': parse_number(it.get('valor_total') or it.get('total') or it.get('valor')),
                'codigo': it.get('codigo') or it.get('cod') or None,
                'ncm': it.get('ncm') or None,
                'cfop': it.get('cfop') or None,
                'cst': it.get('cst') or it.get('csosn') or None,
            })
    out['itens'] = items

    # top-level normalizations
    out['numero_nota'] = out.get('numero_nota') or src.get('numero_nota') or None
    out['chave_acesso'] = (src.get('chave_acesso') or out.get('chave_acesso') or None)
    out['data_emissao'] = parse_date(out.get('data_emissao') or src.get('data_emissao') or None)
    out['natureza_operacao'] = out.get('natureza_operacao') or src.get('natureza_operacao') or None
    out['forma_pagamento'] = out.get('forma_pagamento') or src.get('forma_pagamento') or None
    out['valor_total'] = parse_number(out.get('valor_total') or src.get('valor_total') or None)

    # keep original raw_extracted hints in _meta if present
    if '_meta' in src and isinstance(src['_meta'], dict):
        out['_meta'] = src['_meta']

    return out


def compute_aggregates(extracted):
    """Compute numeric aggregates from normalized extracted data.
    Returns dict with 'valor_total_calc' and 'impostos_calc' containing numeric values.
    """
    try:
        if not extracted or not isinstance(extracted, dict):
            return {"valor_total_calc": None, "impostos_calc": {"icms": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0}}

        def to_num(x):
            """Robust number parsing:
            - if both '.' and ',' appear assume '.' is thousand separator and ',' is decimal
            - if only ',' appears treat it as decimal separator
            - if only '.' appears, decide: if it looks like a decimal with two digits keep it, else treat dots as thousand separators
            """
            try:
                if x is None:
                    return None
                if isinstance(x, (int, float)):
                    return float(x)
                s = str(x).strip()
                if not s:
                    return None
                # keep only digits and separators
                s = re.sub(r"[^0-9\.,-]", "", s)
                if '.' in s and ',' in s:
                    s = s.replace('.', '').replace(',', '.')
                elif ',' in s and '.' not in s:
                    s = s.replace('.', '').replace(',', '.')
                elif '.' in s and ',' not in s:
                    parts = s.split('.')
                    if len(parts) == 2 and len(parts[1]) == 2:
                        # looks like decimal with two digits
                        s = s
                    else:
                        # treat dots as thousand separators
                        s = s.replace('.', '')
                if s in ['', '-', ',', '.']:
                    return None
                return float(s)
            except Exception:
                return None

        # Compute both top-level and items-sum, prefer items sum when it looks reliable
        top_vt = to_num(extracted.get('valor_total'))
        items = extracted.get('itens') or []
        sum_items = 0.0
        items_count = 0
        for it in items:
            try:
                v = to_num(it.get('valor_total'))
            except Exception:
                v = None
            if v is not None:
                sum_items += v
                items_count += 1

        # Decide final valor_total_calc: prefer sum_items when items_count>0 and difference is notable
        vt = None
        if items_count > 0 and sum_items > 0:
            # if top_vt missing or clearly different, prefer sum_items
            if top_vt is None or abs(sum_items - top_vt) > 0.5:
                vt = sum_items
            else:
                # close agreement, prefer the more explicit top value
                vt = top_vt
        else:
            vt = top_vt

        impostos = extracted.get('impostos') or {}
        icms = to_num((impostos.get('icms') or {}).get('valor') if isinstance(impostos.get('icms'), dict) else impostos.get('icms')) or 0.0
        ipi = to_num((impostos.get('ipi') or {}).get('valor') if isinstance(impostos.get('ipi'), dict) else impostos.get('ipi')) or 0.0
        pis = to_num((impostos.get('pis') or {}).get('valor') if isinstance(impostos.get('pis'), dict) else impostos.get('pis')) or 0.0
        cofins = to_num((impostos.get('cofins') or {}).get('valor') if isinstance(impostos.get('cofins'), dict) else impostos.get('cofins')) or 0.0

        return {
            "valor_total_calc": vt if vt is not None else 0.0,
            "impostos_calc": {"icms": icms, "ipi": ipi, "pis": pis, "cofins": cofins}
        }
    except Exception as e:
        print(f"[AGG] compute_aggregates failed: {e}", file=sys.stderr)
        return {"valor_total_calc": None, "impostos_calc": {"icms": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0}}


def _extract_json_text_from_raw(s: str):
    """Helper: pull JSON object literal from raw LLM output (same logic used in processing).
    Returns the JSON string or None.
    """
    if not s or not isinstance(s, str):
        return None
    import re
    m = re.search(r'```json\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'```\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
    if m2:
        return m2.group(1).strip()
    first = s.find('{')
    last = s.rfind('}')
    if first != -1 and last != -1 and last > first:
        return s[first:last+1]
    return None


def process_document(doc_id: str, temp_path: str, file_name: str):
    # Use configured POPPLER_PATH (env override or repo-local default) when available.
    # pdf2image.convert_from_path accepts None to rely on system defaults; pass POPPLER_PATH when set.
    poppler_path = POPPLER_PATH
    try:
        print(f"[PROCESSAMENTO] {doc_id} - Iniciando preprocessamento", file=sys.stderr)
        documents_db[doc_id]["status"] = "preprocessamento"
        documents_db[doc_id]["progress"] = 15
        save_documents_db()

        print(f"[PROCESSAMENTO] {doc_id} - Iniciando OCR", file=sys.stderr)
        documents_db[doc_id]["status"] = "ocr"
        documents_db[doc_id]["progress"] = 40
        save_documents_db()

        ext = os.path.splitext(file_name)[1].lower()
        ocr_text = ""
        if ext == ".pdf":
            # Try to extract selectable text from the PDF first (no Tesseract needed).
            # This helps processing when Tesseract is not installed on the host.
            try:
                from PyPDF2 import PdfReader
                pages_text = []
                with open(temp_path, 'rb') as _f:
                    reader = PdfReader(_f)
                    for p in reader.pages:
                        try:
                            pages_text.append(p.extract_text() or "")
                        except Exception:
                            pages_text.append("")
                ocr_text = "\n\n".join(pages_text).strip()
            except Exception:
                # PyPDF2 not available or failed - try pdfminer if present
                try:
                    from pdfminer.high_level import extract_text
                    try:
                        ocr_text = extract_text(temp_path) or ""
                    except Exception:
                        ocr_text = ""
                except Exception:
                    ocr_text = ""

            # If no selectable text found, fall back to image-based OCR if Tesseract is available.
            if not ocr_text:
                try:
                    try:
                        _ = pytesseract.get_tesseract_version()
                        tesseract_available = True
                    except Exception:
                        tesseract_available = False

                    if tesseract_available:
                        images = pdf2image.convert_from_path(temp_path, poppler_path=poppler_path)
                        ocr_text = "\n\n".join([pytesseract.image_to_string(img, lang="por") for img in images])
                    else:
                        # No selectable text and no Tesseract: raise a clear error to be recorded in the DB
                        raise RuntimeError(
                            "Nenhum texto selecionável encontrado no PDF e o Tesseract não está disponível. "
                            "Instale o Tesseract ou adicione PyPDF2/pdfminer.six ao ambiente."
                        )
                except Exception:
                    # Let outer exception handler record the error in the DB
                    raise
        elif ext in [".jpg", ".jpeg", ".png"]:
            from PIL import Image
            img = Image.open(temp_path)
            ocr_text = pytesseract.image_to_string(img, lang="por")
        elif ext == ".xml":
            import xml.etree.ElementTree as ET
            tree = ET.parse(temp_path)
            root = tree.getroot()
            ocr_text = "\n".join([elem.text for elem in root.iter() if elem.text])
        elif ext == ".csv":
            import csv
            with open(temp_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                ocr_text = "\n".join([", ".join(row) for row in reader])
        else:
            raise ValueError(f"Formato de arquivo não suportado: {ext}")

        documents_db[doc_id]["ocr_text"] = ocr_text
        save_documents_db()

        print(f"[PROCESSAMENTO] {doc_id} - Iniciando NLP", file=sys.stderr)
        documents_db[doc_id]["status"] = "nlp"
        documents_db[doc_id]["progress"] = 70
        save_documents_db()

        prompt = ChatPromptTemplate.from_template(
            """
            Extraia os principais campos fiscais do texto abaixo e retorne um objeto JSON com os seguintes campos. Se algum campo não for encontrado, preencha com null. Considere variações de nomes, sinônimos, abreviações e formatos comuns usados em notas fiscais brasileiras, cupons fiscais, recibos, pedidos e documentos similares. Identifique campos mesmo que estejam com nomes diferentes, abreviados, em ordem distinta ou ausentes. Exemplos de variações: 'Razão Social', 'Empresa', 'Emitente', 'Fornecedor', 'Destinatário', 'Cliente', 'CNPJ', 'CPF', 'IE', 'Inscrição Estadual', 'Endereço', 'Rua', 'Logradouro', 'CFOP', 'CST', 'NCM', 'CSOSN', 'Data', 'Emissão', 'Nota', 'Chave', 'Pagamento', 'Produto', 'Descrição', 'Qtd', 'Unidade', 'Valor', 'Total', 'Recibo', 'Pedido', 'Cupom', etc. Use padrões, contexto e inferência para mapear corretamente, mesmo em documentos não estruturados. Campos:
            - emitente: razao_social, cnpj, inscricao_estadual, endereco
            - destinatario: razao_social, cnpj, inscricao_estadual, endereco
            - itens: descricao, quantidade, unidade, valor_unitario, valor_total
            - impostos: icms (aliquota, base_calculo, valor), ipi (valor), pis (valor), cofins (valor)
            - codigos_fiscais: cfop, cst, ncm, csosn
            - outros: numero_nota, chave_acesso, data_emissao, natureza_operacao, forma_pagamento, valor_total
            Retorne apenas o JSON, sem explicações ou markdown. Se não encontrar campos fiscais, tente extrair os principais dados financeiros e de identificação presentes. Texto extraído:
            {ocr_text}
            """
        )

        # Call the LLM but don't let LLM failures abort processing; fall back to heuristics.
        raw_extracted = None
        parsed_extracted = None
        try:
            # Build a fallback list of free models (dynamically fetched if possible)
            try:
                candidate_models = get_openrouter_free_models(limit=20)
            except Exception:
                candidate_models = [OPENROUTER_MODEL, "minimax/minimax-m2:free"]
            # ensure our configured preferred model is first
            models_to_try = []
            if OPENROUTER_MODEL:
                models_to_try.append(OPENROUTER_MODEL)
            for m in candidate_models:
                if m and m not in models_to_try:
                    models_to_try.append(m)

            raw_extracted = None
            last_exc = None
            succeeded = False
            # rotate through models on auth/rate-limit errors; use small backoff between attempts
            sleep_base = 0.5
            for idx, model_name in enumerate(models_to_try):
                try:
                    try:
                        print(f"[LLM] {doc_id} - attempting model={model_name} (masked key={_mask_key(OPENROUTER_API_KEY)})", file=sys.stderr)
                    except Exception:
                        pass
                    llm = ChatOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1", model=model_name)
                    chain = prompt | llm
                    result = chain.invoke({"ocr_text": ocr_text})
                    raw_extracted = result.content if hasattr(result, "content") else str(result)
                    succeeded = True
                    if idx != 0:
                        print(f"[LLM] {doc_id} - succeeded with fallback model {model_name}", file=sys.stderr)
                    break
                except Exception as e:
                    last_exc = e
                    msg = str(e)
                    print(f"[LLM] {doc_id} - LLM call failed for model {model_name}: {e}", file=sys.stderr)
                    # If auth-like or rate-limit, try next model; otherwise stop trying
                    low = msg.lower()
                    is_auth = ('401' in msg or 'user not found' in low or 'unauthoriz' in low)
                    is_rate = ('429' in msg or 'rate limit' in low or 'free-models-per-day' in low or 'rate_limit' in low)
                    if is_rate or is_auth:
                        # sleep a bit (exponential backoff) before trying next model
                        try:
                            import time
                            time.sleep(min(5, sleep_base * (2 ** idx)))
                        except Exception:
                            pass
                        continue
                    else:
                        break
            if not succeeded:
                raw_extracted = f"LLM Error: {str(last_exc)}" if last_exc else None
        except Exception as e:
            # Defensive: any unexpected error here should be recorded and processing continue via fallback heuristics
            raw_extracted = f"LLM Error: {str(e)}"
            print(f"[LLM] {doc_id} - unexpected LLM processing error: {e}", file=sys.stderr)

        # try to parse LLM JSON output (if any)
        def _extract_json_text(s: str):
            if not s or not isinstance(s, str):
                return None
            # Common cases: code fences like ```json { ... } ``` or plain JSON text.
            import re
            # Try fenced JSON first (non-greedy)
            m = re.search(r'```json\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
            if m:
                return m.group(1).strip()
            # Try generic code fence without language
            m2 = re.search(r'```\s*(\{.*?\})\s*```', s, flags=re.DOTALL)
            if m2:
                return m2.group(1).strip()
            # Fallback: take the substring between the first '{' and the last '}'
            first = s.find('{')
            last = s.rfind('}')
            if first != -1 and last != -1 and last > first:
                return s[first:last+1]
            return None

        try:
            candidate_raw = raw_extracted if raw_extracted is not None else ''
            candidate_text = _extract_json_text(candidate_raw)
            parsed_extracted = None
            if candidate_text:
                try:
                    parsed_extracted = json.loads(candidate_text)
                except Exception:
                    # last resort: try to sanitize common OCR/LLM artifacts
                    try:
                        import re
                        cleaned = re.sub(r"[\x00-\x1f]+", "", candidate_text)
                        parsed_extracted = json.loads(cleaned)
                    except Exception:
                        parsed_extracted = None
            else:
                parsed_extracted = None
        except Exception:
            parsed_extracted = None

        # Always compute a cheap heuristic fallback from OCR text. We'll use it to repair
        # obvious bad LLM outputs (for example when the LLM put a CPF-like token into valor_total).
        try:
            fallback = simple_receipt_parser(ocr_text)
        except Exception:
            fallback = {}

        # Smart merge: prefer parsed_extracted but replace clearly invalid fields with fallback values.
        def looks_like_cpf(s):
            if not s: return False
            ss = str(s)
            import re
            if re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", ss):
                return True
            digits = re.sub(r'\D', '', ss)
            return len(digits) == 11

        def safe_parse_number_candidate(x):
            # try to coerce numeric-looking strings; return float or None
            try:
                if x is None: return None
                if isinstance(x, (int, float)): return float(x)
                s = str(x).strip()
                s2 = s.replace('.', '').replace(',', '.')
                # reject CPF-like tokens
                if looks_like_cpf(s):
                    return None
                return float(s2)
            except Exception:
                return None

        def merge_extracted_sources(parsed, fallback, ocr_text, record):
            """Merge parsed LLM output (parsed), heuristic fallback (fallback), OCR text and other record sources.
            Returns a tuple (merged_dict, meta) where meta is a dict mapping field paths to source names
            (e.g., 'llm', 'fallback', 'ocr', 'specialist'). This aggressively fills missing item textual fields
            from whichever source has non-garbage content.
            """
            try:
                meta = {}
                # Start with parsed if available, otherwise fallback
                outm = {}
                if isinstance(parsed, dict):
                    outm = dict(parsed)
                    for k in parsed.keys():
                        meta[k] = 'llm'
                elif isinstance(fallback, dict):
                    outm = dict(fallback)
                    for k in fallback.keys():
                        meta[k] = 'fallback'

                # Top-level merge helpers
                def prefer_field(path, *candidates):
                    """Set outm[path] from first candidate that is non-garbage. Candidates are tuples (value, source)."""
                    for val, src in candidates:
                        if val is None:
                            continue
                        # prefer dict/list non-empty or non-garbage strings
                        if isinstance(val, str):
                            if val.strip() and not (len(val.strip()) <= 3):
                                outm[path] = val
                                meta[path] = src
                                return
                        elif isinstance(val, (int, float)):
                            outm[path] = val
                            meta[path] = src
                            return
                        elif isinstance(val, dict) or isinstance(val, list):
                            # accept non-empty
                            try:
                                if val:
                                    outm[path] = val
                                    meta[path] = src
                                    return
                            except Exception:
                                pass

                # numeric total preference
                try:
                    prefer_field('valor_total', (parsed and parsed.get('valor_total'), 'llm'), (fallback and fallback.get('valor_total'), 'fallback'))
                except Exception:
                    pass

                # destinatario razao_social
                try:
                    pd = (parsed.get('destinatario') if isinstance(parsed, dict) else None) or {}
                    fd = (fallback.get('destinatario') if isinstance(fallback, dict) else None) or {}
                    prefer_field('destinatario', (pd.get('razao_social') if pd else None, 'llm'), (fd.get('razao_social') if fd else None, 'fallback'))
                except Exception:
                    pass

                # Items: try to align lists. We'll build merged_items
                merged_items = []
                parsed_items = parsed.get('itens') if isinstance(parsed, dict) and isinstance(parsed.get('itens'), list) else []
                fallback_items = fallback.get('itens') if isinstance(fallback, dict) and isinstance(fallback.get('itens'), list) else []

                # Candidate items from OCR/specialist
                ocr_cand = []
                try:
                    # Try specialist agent to extract items from raw OCR if available
                    try:
                        import importlib
                        sa = importlib.import_module('backend.agents.specialist_agent')
                    except Exception:
                        sa = None
                    if sa:
                        # pass record and current outm (best-effort)
                        rec_copy = record or {}
                        cand_lines = sa._find_product_section_lines(sa._text_sources(rec_copy)) if hasattr(sa, '_find_product_section_lines') else []
                        if cand_lines:
                            ocr_cand = sa._extract_items_from_lines(cand_lines) if hasattr(sa, '_extract_items_from_lines') else []
                    else:
                        # simple heuristic using fallback parser on OCR text
                        if ocr_text:
                            try:
                                fr = simple_receipt_parser(ocr_text)
                                if fr and fr.get('itens'):
                                    ocr_cand = fr.get('itens')
                            except Exception:
                                ocr_cand = []
                except Exception:
                    ocr_cand = []

                # Choose base list: prefer parsed_items if present, else fallback_items, else ocr_cand
                base = parsed_items or fallback_items or ocr_cand
                # If lengths differ, still try to merge by index where possible
                max_len = max(len(parsed_items), len(fallback_items), len(ocr_cand), len(base))
                for i in range(max_len):
                    p = parsed_items[i] if i < len(parsed_items) else None
                    f = fallback_items[i] if i < len(fallback_items) else None
                    o = ocr_cand[i] if i < len(ocr_cand) else None
                    item = {}
                    # for each field, take from parsed then fallback then ocr
                    for fld in ['descricao', 'quantidade', 'unidade', 'valor_unitario', 'valor_total', 'codigo', 'ncm', 'cfop', 'cst']:
                        v = None
                        src = None
                        try:
                            if p and isinstance(p, dict) and p.get(fld) not in [None, '', []]:
                                v = p.get(fld); src = 'llm'
                            elif f and isinstance(f, dict) and f.get(fld) not in [None, '', []]:
                                v = f.get(fld); src = 'fallback'
                            elif o and isinstance(o, dict) and o.get(fld) not in [None, '', []]:
                                v = o.get(fld); src = 'ocr'
                            # final heuristics: if descricao still missing, try to find a likely line in OCR containing money matching valor_total
                            if fld == 'descricao' and not v and ocr_text:
                                try:
                                    # find lines where next line contains price
                                    lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
                                    for idx, ln in enumerate(lines[:-1]):
                                        if re.search(r'[0-9]+[\.,][0-9]{2}', lines[idx+1]):
                                            # pick this as candidate
                                            v = ln[:200]; src = 'ocr'
                                            break
                                except Exception:
                                    pass
                        except Exception:
                            v = None; src = None
                        item[fld] = v
                        if src:
                            meta[f'itens[{i}].{fld}'] = src
                    # Only append items that have at least a valor_total or descricao
                    if any(item.get(k) for k in ('descricao', 'valor_total', 'valor_unitario')):
                        merged_items.append(item)

                if merged_items:
                    outm['itens'] = merged_items
                    meta['itens'] = 'merged'

                # As a last step, run enrichment_agent to further fill fields
                try:
                    import importlib
                    ea = importlib.import_module('backend.agents.enrichment_agent')
                    # enrichment_agent expects a full record; build temp record
                    temp_rec = dict(record) if isinstance(record, dict) else {'ocr_text': ocr_text}
                    temp_rec['raw_extracted'] = parsed or temp_rec.get('raw_extracted')
                    temp_rec['ocr_text'] = ocr_text
                    new_extracted, info = ea.enrich_record({'extracted_data': outm, 'raw_extracted': parsed or {}, 'ocr_text': ocr_text})
                    if isinstance(new_extracted, dict):
                        outm = new_extracted
                        meta['enrichment'] = 'enrichment_agent'
                except Exception:
                    pass

                return outm, meta
            except Exception:
                return (parsed or fallback or {}), {}

        final_extracted = None
        if parsed_extracted is None:
            final_extracted = fallback
        else:
            try:
                # merge LLM parsed output, fallback heuristics, OCR text and specialist/enrichment
                merged, meta = merge_extracted_sources(parsed_extracted, fallback, ocr_text, documents_db.get(doc_id, {}))
                final_extracted = merged
                if isinstance(final_extracted, dict):
                    final_extracted.setdefault('_meta', {})
                    try:
                        final_extracted['_meta'].update(meta or {})
                    except Exception:
                        pass
            except Exception:
                final_extracted = parsed_extracted or fallback

        # store raw LLM output and the normalized extracted data
        documents_db[doc_id]["raw_extracted"] = raw_extracted
        # Normalize defensively: on failure try to normalize the fallback, otherwise store an empty dict.
        try:
            normalized = normalize_extracted(final_extracted) if final_extracted is not None else {}
        except Exception:
            try:
                normalized = normalize_extracted(fallback) if isinstance(fallback, dict) else {}
            except Exception:
                normalized = {}
        # Ensure extracted_data is always a dict (clients expect an object). Keep raw_extracted separate for debugging.
        documents_db[doc_id]["extracted_data"] = normalized if isinstance(normalized, dict) else {}
        # merged_extracted already prioritized parsed/fallback/ocr and ran enrichment; no extra repair step needed here
        # compute and persist aggregates for reliable dashboard aggregation
        try:
            aggregates = compute_aggregates(normalized if isinstance(normalized, dict) else {})
            documents_db[doc_id]["aggregates"] = aggregates
        except Exception as e:
            print(f"[AGG] failed to compute aggregates for {doc_id}: {e}", file=sys.stderr)
            documents_db[doc_id]["aggregates"] = {"valor_total_calc": None, "impostos_calc": {"icms":0.0,"ipi":0.0,"pis":0.0,"cofins":0.0}}
        save_documents_db()

        print(f"[PROCESSAMENTO] {doc_id} - Iniciando validação", file=sys.stderr)
        documents_db[doc_id]["status"] = "validacao"
        documents_db[doc_id]["progress"] = 90
        save_documents_db()

        # finalização
        print(f"[PROCESSAMENTO] {doc_id} - Finalizado", file=sys.stderr)
        documents_db[doc_id]["status"] = "finalizado"
        documents_db[doc_id]["progress"] = 100
        save_documents_db()

    except Exception as e:
        print(f"[PROCESSAMENTO] {doc_id} - ERRO: {str(e)}", file=sys.stderr)
        documents_db[doc_id]["status"] = "erro"
        documents_db[doc_id]["progress"] = 100
        # Store the error separately to avoid changing the type of `extracted_data` (which is expected to be a dict).
        documents_db[doc_id]["extracted_error"] = f"Erro: {str(e)}"
        # keep extracted_data as-is (None or dict) so clients don't crash when reading it
        documents_db[doc_id]["aggregates"] = {"valor_total_calc": None, "impostos_calc": {"icms":0.0,"ipi":0.0,"pis":0.0,"cofins":0.0}}
        save_documents_db()


@app.post("/api/v1/documents/upload")
async def upload_document(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """Accept multiple files uploaded as multipart/form-data with field name 'files'.
    Returns a list of created document ids.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    created_ids = []
    tmp_dir = tempfile.gettempdir()
    for file in files:
        doc_id = str(uuid.uuid4())
        tmp_path = os.path.join(tmp_dir, f"{doc_id}_{file.filename}")
        content = await file.read()
        with open(tmp_path, 'wb') as f:
            f.write(content)

        # try to store original uploaded content as text for XML/CSV debug (best-effort)
        raw_file_text = None
        try:
            raw_file_text = content.decode('utf-8')
        except Exception:
            try:
                raw_file_text = content.decode('latin-1')
            except Exception:
                raw_file_text = None

        documents_db[doc_id] = {
            "id": doc_id,
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "status": "ingestao",
            "progress": 5,
            "ocr_text": None,
            "raw_file": raw_file_text,
            "tmp_path": tmp_path,
            "raw_extracted": None,
            "extracted_data": None
        }
        save_documents_db()

        # schedule background processing
        if background_tasks is not None:
            background_tasks.add_task(process_document, doc_id, tmp_path, file.filename)
        else:
            process_document(doc_id, tmp_path, file.filename)

        created_ids.append(doc_id)

    return {"message": f"Scheduled {len(created_ids)} file(s) for processing", "document_ids": created_ids}


@app.get("/api/v1/documents/{doc_id}/results")
async def get_results(doc_id: str):
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    # return stored document record; clients can inspect raw_extracted for debugging
    return documents_db[doc_id]


@app.get("/api/v1/documents/{doc_id}/download")
async def download_document(doc_id: str):
    """Return the original uploaded file (stream) if available."""
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    rec = documents_db[doc_id]
    tmp_path = rec.get('tmp_path')
    if not tmp_path or not os.path.exists(tmp_path):
        raise HTTPException(status_code=404, detail="Original file not available")
    from fastapi.responses import FileResponse
    return FileResponse(tmp_path, media_type='application/octet-stream', filename=rec.get('filename'))


@app.get("/api/v1/documents")
async def list_documents():
    # return a list of available documents with brief metadata
    try:
        docs = []
        for k, v in documents_db.items():
            # include normalized extracted_data (if available) so clients can compute aggregates
            # include small previews of ocr_text and raw_extracted (trimmed) to allow client-side heuristics
            ocr = v.get('ocr_text') or ''
            raw_ex = v.get('raw_extracted') or ''
            docs.append({
                "id": k,
                "filename": v.get("filename"),
                "uploaded_at": v.get("uploaded_at"),
                "status": v.get("status"),
                "progress": v.get("progress"),
                "extracted_data": v.get("extracted_data"),
                "aggregates": v.get("aggregates"),
                "ocr_text": (ocr[:2000] + ('...' if len(ocr) > 2000 else '')) if ocr else None,
                    "raw_extracted": (raw_ex[:2000] + ('...' if len(raw_ex) > 2000 else '')) if raw_ex else None,
            })
        # sort by uploaded_at desc if present
        docs.sort(key=lambda x: x.get('uploaded_at') or '', reverse=True)
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/documents/{doc_id}/enrich")
async def enrich_document_endpoint(doc_id: str):
    """Run the enrichment heuristics on a single stored document and persist changes.
    Useful to repair records where some fields are null or missing.
    """
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        import importlib
        # try multiple import paths for robustness (running from different CWDs)
        tried = []
        enrichment_agent = None
        candidates = ['backend.agents.enrichment_agent', 'agents.enrichment_agent', 'backend.agents.enrichment_agent']
        for cand in candidates:
            try:
                enrichment_agent = importlib.import_module(cand)
                break
            except Exception as e:
                tried.append((cand, str(e)))
        if enrichment_agent is None:
            raise ImportError(f"could not import enrichment_agent, tried: {tried}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment agent import failed: {e}")

    rec = documents_db[doc_id]
    try:
        new_extracted, info = enrichment_agent.enrich_record(rec)
        documents_db[doc_id]["extracted_data"] = new_extracted
        documents_db[doc_id]["aggregates"] = info.get('aggregates')
        save_documents_db()
        return {"message": "enriched", "filled": info.get('report', {}).get('filled', {}), "aggregates": documents_db[doc_id]["aggregates"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/repair_from_raw")
def admin_repair_from_raw(doc_id: str):
    """Admin: reparses the `raw_extracted` JSON for a stored document and replaces
    `extracted_data` + `aggregates` if the parsed JSON is valid. Returns details.
    """
    if doc_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    rec = documents_db[doc_id]
    raw = rec.get('raw_extracted')
    if not raw or not isinstance(raw, str):
        raise HTTPException(status_code=400, detail="No raw_extracted JSON found for this document")
    candidate = _extract_json_text_from_raw(raw)
    if not candidate:
        raise HTTPException(status_code=400, detail="No JSON object detected in raw_extracted")
    try:
        parsed = json.loads(candidate)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parsed JSON invalid: {e}")

    # normalize and compute aggregates
    try:
        normalized = normalize_extracted(parsed) if isinstance(parsed, dict) else {}
    except Exception as e:
        normalized = {}
    try:
        ag = compute_aggregates(normalized if isinstance(normalized, dict) else {})
    except Exception:
        ag = {'valor_total_calc': None, 'impostos_calc': {'icms': 0.0, 'ipi': 0.0, 'pis': 0.0, 'cofins': 0.0}}

    # cautious replace: only overwrite if normalized has items or appears richer
    replaced = False
    cur = rec.get('extracted_data') or {}
    try:
        cur_items = (cur.get('itens') or []) if isinstance(cur, dict) else []
        new_items = (normalized.get('itens') or []) if isinstance(normalized, dict) else []
        if new_items and (not cur_items or any((not it.get('descricao') for it in cur_items))):
            documents_db[doc_id]['extracted_data'] = normalized
            documents_db[doc_id]['aggregates'] = ag
            replaced = True
            save_documents_db()
    except Exception:
        # as a safe fallback, persist normalized anyway
        documents_db[doc_id]['extracted_data'] = normalized
        documents_db[doc_id]['aggregates'] = ag
        save_documents_db()

    return {"doc_id": doc_id, "replaced": replaced, "aggregates": documents_db[doc_id].get('aggregates')}


@app.post("/api/v1/admin/recompute_aggregates")
def admin_recompute_aggregates():
    """Admin: recompute aggregates for all stored documents from their `extracted_data`.
    Useful when agent logic was changed and you want to refresh dashboard metrics.
    Returns number of documents updated.
    """
    updated = 0
    try:
        for k, rec in documents_db.items():
            try:
                ed = rec.get('extracted_data') or {}
                ag = compute_aggregates(ed if isinstance(ed, dict) else {})
                # only update if different (simple numeric check)
                prev = rec.get('aggregates') or {}
                prev_v = prev.get('valor_total_calc') if isinstance(prev, dict) else None
                if ag.get('valor_total_calc') != prev_v:
                    documents_db[k]['aggregates'] = ag
                    updated += 1
            except Exception:
                continue
        save_documents_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"updated": updated}


@app.post("/api/v1/admin/reload_db")
def admin_reload_db():
    """Admin: force reload of `documents_db.json` from disk into memory.
    Useful when the on-disk DB was restored and the running process needs to pick up the changes.
    """
    try:
        # reload from disk (persistence.load_documents_db may replace the in-module object)
        load_documents_db()
        # ensure our module-level reference points to the fresh persistence store
        try:
            globals()['documents_db'] = persistence.documents_db
        except Exception:
            pass
        count = len(persistence.documents_db)
        return {"reloaded": True, "loaded_records": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/clear_db")
def admin_clear_db(backup: bool = True):
    """Admin: safely backup the current on-disk DB and replace it with an empty store.
    This endpoint will:
      - copy the current DATA_STORE_PATH to DATA_STORE_PATH.cleared_<ts> (if exists)
      - replace the on-disk DB with an empty JSON object
      - clear the in-memory `documents_db` and persist the empty store
    Returns a summary with backup filename (if created) and new record count (0 on success).
    """
    try:
        path = DATA_STORE_PATH
        backup_path = None
        if os.path.exists(path) and backup:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{path}.cleared_{ts}"
            try:
                shutil.copy2(path, backup_path)
            except Exception as e:
                # best-effort backup but continue
                print(f"[PERSIST] warning: backup during clear_db failed: {e}", file=sys.stderr)
        # clear in-memory store
        try:
            # update persistence module store as well
            persistence.documents_db = {}
            globals()['documents_db'] = persistence.documents_db
        except Exception:
            documents_db.clear()
        # persist empty DB to disk
        save_documents_db()
        return {"cleared": True, "backup": os.path.basename(backup_path) if backup_path else None, "loaded_records": len(persistence.documents_db or documents_db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/db_info")
def admin_db_info():
    """Return the absolute path and some metadata about the on-disk documents DB the running
    process will load from `persistence.DATA_STORE_PATH`. Useful for debugging which file
    the running server reads.
    """
    try:
        path = DATA_STORE_PATH
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else None
        preview = None
        if exists:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    preview = f.read(2000)
            except Exception:
                preview = None
        return {"path": os.path.abspath(path), "exists": exists, "size": size, "preview": preview}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
                        
