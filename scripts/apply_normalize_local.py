import json, re
from pathlib import Path
ROOT = Path(__file__).parent.parent
p = ROOT.joinpath('backend', 'api', 'documents_db.json')
allrec = json.loads(p.read_text(encoding='utf-8'))
key='4d8a92f8-3c64-44a5-b865-1a68a6782549'
rec = allrec[key]
raw = rec.get('raw_extracted') or ''
# extract json like main._extract_json_text
m = re.search(r'```json\s*(\{.*?\})\s*```', raw, flags=re.DOTALL)
if m:
    ct = m.group(1)
else:
    m2 = re.search(r'```\s*(\{.*?\})\s*```', raw, flags=re.DOTALL)
    if m2:
        ct = m2.group(1)
    else:
        first = raw.find('{')
        last = raw.rfind('}')
        ct = raw[first:last+1] if first!=-1 and last!=-1 and last>first else None

print('candidate length', len(ct) if ct else None)
parsed = json.loads(ct)
print('parsed item:', parsed.get('itens')[0])

# replicate normalize_extracted from main.py

def normalize_extracted(extracted):
    import re
    if not extracted or not isinstance(extracted, dict):
        return extracted

    out = {}

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
        if len(ss) <= 3:
            return True
        low = ss.lower()
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
            ss = re.sub(r"[^0-9\.,-]", "", ss)
            if '.' in ss and ',' in ss:
                ss = ss.replace('.', '').replace(',', '.')
            elif ',' in ss:
                ss = ss.replace('.', '').replace(',', '.')
            elif '.' in ss:
                parts = ss.split('.')
                if len(parts) == 2 and len(parts[1]) == 2:
                    ss = ss
                else:
                    ss = ss.replace('.', '')
            if ss in ['', '-', ',', '.']:
                return None
            return float(ss)
        except Exception:
            return None

    def parse_date(s):
        if not s: return None
        s = str(s).strip()
        m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s)
        if m:
            d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            return d
        m2 = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m2:
            return s
        return None

    src = dict(extracted)
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

norm = normalize_extracted(parsed)
print('normalized item:', norm.get('itens')[0])
