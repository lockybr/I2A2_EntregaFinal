#!/usr/bin/env python3
"""Re-normalize all entries in documents_db.json using normalize_extracted.
This script imports normalize_extracted, merge_dicts and simple_receipt_parser from main.py
and writes back normalized `extracted_data` entries. Run it from the backend directory.
"""
import json
import os
import sys

# ensure backend package imports main.py from same folder
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Try to import helpers from the real backend. If that fails (missing deps),
# fall back to local lightweight implementations so this script can run in
# a minimal Python environment.
try:
    from api import main  # type: ignore
    DATA_STORE_PATH = main.DATA_STORE_PATH
    normalize_extracted = main.normalize_extracted
    merge_dicts = main.merge_dicts
    simple_receipt_parser = main.simple_receipt_parser
    print("Imported helpers from api.main")
except Exception as e:
    print(f"Could not import api.main (continuing with local helpers): {e}")

    # Local implementations (kept small and dependency free)
    import re

    DATA_STORE_PATH = os.path.join(HERE, 'api', 'documents_db.json')

    def merge_dicts(dst, src):
        if not isinstance(dst, dict) or not isinstance(src, dict):
            return dst
        for k, v in src.items():
            if k not in dst or dst[k] is None:
                dst[k] = v
            else:
                if isinstance(v, dict) and isinstance(dst[k], dict):
                    merge_dicts(dst[k], v)
                elif isinstance(v, list) and not dst[k]:
                    dst[k] = v
        return dst

    def simple_receipt_parser(text: str):
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
        if lines:
            out['emitente']['razao_social'] = lines[0]

        total_re = re.compile(r'(?:total|valor total|valor|total\s*[:\-])\s*[:\-]?\s*R?\$?\s*([0-9]+[\.,][0-9]{2})', re.IGNORECASE)
        any_money_re = re.compile(r'R?\$\s*([0-9]+[\.,][0-9]{2})')
        for ln in reversed(lines[-10:]):
            m = total_re.search(ln)
            if m:
                out['valor_total'] = m.group(1).replace(',', '.')
                break
        if out.get('valor_total') is None:
            for ln in reversed(lines):
                m2 = any_money_re.search(ln)
                if m2:
                    out['valor_total'] = m2.group(1).replace(',', '.')
                    break

        item_line_re = re.compile(r'^(.{3,60})\s+(\d+)\s+R?\$?\s*([0-9]+[\.,][0-9]{2})$')
        for ln in lines:
            m = item_line_re.match(ln)
            if m:
                desc = m.group(1).strip()
                qty = m.group(2)
                val = m.group(3).replace(',', '.')
                out['itens'].append({"descricao": desc, "quantidade": qty, "unidade": None, "valor_unitario": val, "valor_total": val})

        if not out['itens']:
            for i, ln in enumerate(lines[:-1]):
                if any_money_re.search(lines[i+1]):
                    amt = any_money_re.search(lines[i+1]).group(1).replace(',', '.')
                    out['itens'].append({"descricao": ln, "quantidade": None, "unidade": None, "valor_unitario": amt, "valor_total": amt})
                    break

        return out

    def normalize_extracted(extracted):
        if not extracted or not isinstance(extracted, dict):
            return extracted

        def only_digits(s):
            if not s: return None
            return re.sub(r'\D', '', str(s)) or None

        def parse_number(s):
            if s is None: return None
            if isinstance(s, (int, float)): return float(s)
            try:
                ss = str(s).strip()
                ss = ss.replace('.', '').replace(',', '.')
                return float(ss)
            except Exception:
                return None

        def parse_date(s):
            if not s: return None
            s = str(s).strip()
            m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
            if m:
                return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            m2 = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
            if m2:
                return s
            return None

        def is_garbage_str(s):
            if s is None: return True
            try:
                ss = str(s).strip()
            except Exception:
                return True
            if not ss: return True
            if len(ss) <= 3:
                return True
            low = ss.lower()
            garbage_tokens = ['recebe', 'visualize', 'boleto', 'nf-e', 'nfe', 'nf e', 'visualizar', 'venda mercadoria']
            for t in garbage_tokens:
                if t in low:
                    return True
            return False

        src = dict(extracted)
        out = {}
        outros = src.pop('outros', {}) if isinstance(src.get('outros', {}), dict) else {}
        for k in ['numero_nota', 'chave_acesso', 'data_emissao', 'natureza_operacao', 'forma_pagamento', 'valor_total']:
            if k in src and src[k] is not None:
                out[k] = src[k]
            elif k in outros and outros[k] is not None:
                out[k] = outros[k]
            else:
                out[k] = src.get(k) if k in src else None

        def normalize_party(p):
            if not p or not isinstance(p, dict): return {"razao_social": None, "cnpj": None, "inscricao_estadual": None, "endereco": None}
            rs = p.get('razao_social') or p.get('nome') or p.get('razao') or None
            if is_garbage_str(rs): rs = None
            cnpj_raw = p.get('cnpj') or p.get('cpf') or p.get('cnpj_emitente')
            cnpj = only_digits(cnpj_raw)
            ie_raw = p.get('inscricao_estadual') or p.get('inscricao') or p.get('ie')
            ie = only_digits(ie_raw)
            endereco = p.get('endereco') or p.get('logradouro') or None
            if endereco and is_garbage_str(endereco): endereco = None
            return {"razao_social": rs, "cnpj": cnpj, "inscricao_estadual": ie, "endereco": endereco}

        out['emitente'] = normalize_party(src.get('emitente') or {})
        out['destinatario'] = normalize_party(src.get('destinatario') or {})

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

        cf = src.get('codigos_fiscais') or {}
        out['codigos_fiscais'] = {
            'cfop': cf.get('cfop') or src.get('cfop') or None,
            'cst': cf.get('cst') or src.get('cst') or None,
            'ncm': cf.get('ncm') or src.get('ncm') or None,
            'csosn': cf.get('csosn') or src.get('csosn') or None,
        }

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

        out['numero_nota'] = out.get('numero_nota') or src.get('numero_nota') or None
        out['chave_acesso'] = (src.get('chave_acesso') or out.get('chave_acesso') or None)
        out['data_emissao'] = parse_date(out.get('data_emissao') or src.get('data_emissao') or None)
        out['natureza_operacao'] = out.get('natureza_operacao') or src.get('natureza_operacao') or None
        out['forma_pagamento'] = out.get('forma_pagamento') or src.get('forma_pagamento') or None
        out['valor_total'] = parse_number(out.get('valor_total') or src.get('valor_total') or None)

        if '_meta' in src and isinstance(src['_meta'], dict):
            out['_meta'] = src['_meta']

        return out

    print(f"Using local DATA_STORE_PATH: {DATA_STORE_PATH}")

# Ensure DB_PATH name is set for the rest of the script
DB_PATH = globals().get('DATA_STORE_PATH')

with open(DB_PATH, 'r', encoding='utf-8') as f:
    db = json.load(f)

updated = 0
for doc_id, rec in db.items():
    print(f"Processing {doc_id} ({rec.get('filename')})")
    raw_extracted = rec.get('raw_extracted')
    parsed = None
    if isinstance(raw_extracted, str):
        cand = raw_extracted.strip()
        try:
            if cand.startswith('```json'):
                cand = cand.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(cand)
        except Exception:
            try:
                # try unescaping
                cand2 = cand.replace('\\n', '\n').replace('\\t', '\t')
                parsed = json.loads(cand2)
            except Exception:
                parsed = None
    existing = rec.get('extracted_data')

    # Compute fallback heuristics early
    heur = simple_receipt_parser(rec.get('ocr_text') or '')

    # helpers to detect CPFs and safely parse numeric candidates
    def looks_like_cpf(s):
        if not s:
            return False
        ss = str(s)
        import re
        if re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", ss):
            return True
        digits = re.sub(r'\D', '', ss)
        return len(digits) == 11

    def safe_parse_number_candidate(x):
        try:
            if x is None:
                return None
            if isinstance(x, (int, float)):
                return float(x)
            s = str(x).strip()
            # reject CPF-like tokens
            if looks_like_cpf(s):
                return None
            s2 = s.replace('.', '').replace(',', '.')
            return float(s2)
        except Exception:
            return None

    def smart_merge(dst, src):
        # dst: parsed (may be None), src: fallback
        if not isinstance(src, dict):
            return dst if isinstance(dst, dict) else src
        if not isinstance(dst, dict):
            return src
        outm = dict(dst)
        try:
            dst_v = dst.get('valor_total')
            src_v = src.get('valor_total')
            if safe_parse_number_candidate(dst_v) is None and safe_parse_number_candidate(src_v) is not None:
                outm['valor_total'] = src_v
        except Exception:
            pass
        try:
            dst_dest = dst.get('destinatario') or {}
            src_dest = src.get('destinatario') or {}
            dst_rs = dst_dest.get('razao_social') if isinstance(dst_dest, dict) else None
            src_rs = src_dest.get('razao_social') if isinstance(src_dest, dict) else None
            def short_or_noise(s):
                if not s:
                    return True
                ss = str(s).strip()
                if len(ss) <= 3:
                    return True
                return False
            if (dst_rs is None or short_or_noise(dst_rs)) and (src_rs is not None and not short_or_noise(src_rs)):
                outm['destinatario'] = dict(dst_dest) if isinstance(dst_dest, dict) else {}
                outm['destinatario']['razao_social'] = src_rs
                if not outm['destinatario'].get('cnpj') and src_dest.get('cnpj'):
                    outm['destinatario']['cnpj'] = src_dest.get('cnpj')
        except Exception:
            pass
        try:
            if (not dst.get('itens')) and src.get('itens'):
                outm['itens'] = src.get('itens')
        except Exception:
            pass
        return outm

    # Decide final extracted: prefer parsed plus smart repairs, else fallback
    if parsed is None:
        final = heur
    else:
        final = smart_merge(parsed, heur)

    try:
        normalized = normalize_extracted(final) if final is not None else final
    except Exception as e:
        print(f"Normalization failed for {doc_id}: {e}")
        normalized = final

    # compute aggregates when possible
    try:
        # try to use compute_aggregates from api.main if available
        if 'api' in sys.modules and hasattr(sys.modules.get('api.main'), 'compute_aggregates'):
            agg = sys.modules.get('api.main').compute_aggregates(normalized if isinstance(normalized, dict) else {})
        else:
            # fallback: simple numeric extraction
            def to_num(x):
                try:
                    if x is None: return None
                    if isinstance(x, (int, float)): return float(x)
                    s = str(x).strip()
                    if not s: return None
                    s = s.replace('.', '').replace(',', '.')
                    return float(s)
                except Exception:
                    return None
            vt = to_num(normalized.get('valor_total')) if isinstance(normalized, dict) else None
            if vt is None:
                s = 0.0
                for it in (normalized.get('itens') or []):
                    v = to_num(it.get('valor_total')) if isinstance(it, dict) else None
                    if v is not None: s += v
                vt = s if s != 0 else None
            imp = (normalized.get('impostos') or {}) if isinstance(normalized, dict) else {}
            icms = to_num((imp.get('icms') or {}).get('valor') if isinstance(imp.get('icms'), dict) else imp.get('icms')) or 0.0
            ipi = to_num((imp.get('ipi') or {}).get('valor') if isinstance(imp.get('ipi'), dict) else imp.get('ipi')) or 0.0
            pis = to_num((imp.get('pis') or {}).get('valor') if isinstance(imp.get('pis'), dict) else imp.get('pis')) or 0.0
            cofins = to_num((imp.get('cofins') or {}).get('valor') if isinstance(imp.get('cofins'), dict) else imp.get('cofins')) or 0.0
            agg = {"valor_total_calc": vt if vt is not None else 0.0, "impostos_calc": {"icms": icms, "ipi": ipi, "pis": pis, "cofins": cofins}}

    except Exception as e:
        print(f"Could not compute aggregates for {doc_id}: {e}")
        agg = {"valor_total_calc": None, "impostos_calc": {"icms":0.0, "ipi":0.0, "pis":0.0, "cofins":0.0}}

    # write back if changed
    if normalized is not None:
        rec['extracted_data'] = normalized
        rec['aggregates'] = agg
        db[doc_id] = rec
        updated += 1

# persist
with open(DB_PATH, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"Done. Updated {updated} records.")
