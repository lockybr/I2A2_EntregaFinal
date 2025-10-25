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
from pydantic import SecretStr

OPENROUTER_API_KEY = SecretStr("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")
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3.1:free"


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

# Simulação de banco em memória (persistida em disco)
DATA_STORE_PATH = os.path.join(os.path.dirname(__file__), 'documents_db.json')
documents_db = {}
_db_lock = threading.Lock()


def load_documents_db():
    global documents_db
    try:
        if os.path.exists(DATA_STORE_PATH):
            with open(DATA_STORE_PATH, 'r', encoding='utf-8') as f:
                documents_db = json.load(f)
        else:
            documents_db = {}
    except Exception as e:
        print(f"[PERSIST] failed to load documents_db: {e}", file=sys.stderr)
        documents_db = {}


def save_documents_db():
    try:
        with _db_lock:
            with open(DATA_STORE_PATH, 'w', encoding='utf-8') as f:
                json.dump(documents_db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[PERSIST] failed to save documents_db: {e}", file=sys.stderr)


# Load persisted DB at startup
load_documents_db()
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
            # replace thousand separators and unify decimal
            ss = ss.replace('.', '').replace(',', '.')
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
            try:
                if x is None:
                    return None
                if isinstance(x, (int, float)):
                    return float(x)
                s = str(x).strip()
                if not s:
                    return None
                s = s.replace('.', '').replace(',', '.')
                return float(s)
            except Exception:
                return None

        # valor_total preference
        vt = to_num(extracted.get('valor_total'))
        if vt is None:
            # sum itens
            items = extracted.get('itens') or []
            s = 0.0
            for it in items:
                v = to_num(it.get('valor_total'))
                if v is not None:
                    s += v
            vt = s if s != 0 else None

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


def process_document(doc_id: str, temp_path: str, file_name: str):
    poppler_path = r"C:\\labz\\fiscal-extraction-system-COMPLETO\\poppler\\Library\\bin"
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
            images = pdf2image.convert_from_path(temp_path, poppler_path=poppler_path)
            ocr_text = "\n".join([pytesseract.image_to_string(img, lang="por") for img in images])
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

        llm = ChatOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1", model=OPENROUTER_MODEL)
        chain = prompt | llm
        result = chain.invoke({"ocr_text": ocr_text})

        raw_extracted = result.content if hasattr(result, "content") else str(result)
        parsed_extracted = None
        try:
            candidate = raw_extracted.strip()
            if candidate.startswith('```json'):
                candidate = candidate.replace('```json', '').replace('```', '').strip()
            parsed_extracted = json.loads(candidate)
        except Exception:
            parsed_extracted = None

        final_extracted = parsed_extracted
        if parsed_extracted is None or all_nulls(parsed_extracted):
            fallback = simple_receipt_parser(ocr_text)
            if parsed_extracted is None:
                final_extracted = fallback
            else:
                try:
                    final_extracted = merge_dicts(parsed_extracted, fallback)
                except Exception:
                    final_extracted = parsed_extracted or fallback

        # store raw LLM output and the normalized extracted data
        documents_db[doc_id]["raw_extracted"] = raw_extracted
        try:
            normalized = normalize_extracted(final_extracted) if final_extracted is not None else None
        except Exception:
            normalized = final_extracted
        documents_db[doc_id]["extracted_data"] = normalized if normalized is not None else raw_extracted
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
        documents_db[doc_id]["extracted_data"] = f"Erro: {str(e)}"
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
                        
