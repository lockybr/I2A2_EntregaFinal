"""
Specialist agent for invoices: tries to recover structured item lines and alternate field names
from OCR/raw_extracted when normalization failed.

Provides:
- refine_extracted(record, extracted) -> (extracted_updated, notes)

This agent focuses on heuristics specific to Brazilian NF-e/DANFE layouts and common cupom formats.
"""
import re
from typing import Dict, Any, List, Tuple, Optional
import json


def _text_sources(record: Dict[str, Any]) -> str:
    parts = []
    if isinstance(record.get('raw_extracted'), dict):
        try:
            parts.append(json.dumps(record.get('raw_extracted'), ensure_ascii=False))
        except Exception:
            parts.append(str(record.get('raw_extracted')))
    elif record.get('raw_extracted'):
        parts.append(str(record.get('raw_extracted')))
    if record.get('ocr_text'):
        parts.append(record.get('ocr_text'))
    if record.get('raw_file'):
        parts.append(str(record.get('raw_file')))
    if record.get('extracted_data') and isinstance(record.get('extracted_data'), dict):
        try:
            parts.append(json.dumps(record.get('extracted_data'), ensure_ascii=False))
        except Exception:
            parts.append(str(record.get('extracted_data')))
    return "\n".join([p for p in parts if p])


# NOTE: removed a malformed/duplicated implementation of _extract_address_parts that
# contained unrelated logic and introduced syntax/indentation errors. The file
# contains a single, defensive implementation of _extract_address_parts further down
# which is the intended authoritative version.


def _extract_address_parts(addr: str) -> Dict[str, Optional[str]]:
    """Defensive and adaptive extraction of CEP, UF, municipio and bairro from a free-form address string.

    The function uses multiple heuristics and validation checks. It aims to avoid false positives
    by validating UF against known Brazilian state codes, normalizing CEP, and applying
    plausibility checks for municipality and neighborhood strings.
    """
    if not addr or not isinstance(addr, str):
        return {'cep': None, 'uf': None, 'municipio': None, 'bairro': None}
    s = addr.strip()
    out = {'cep': None, 'uf': None, 'municipio': None, 'bairro': None}

    # Helper validators
    def _valid_uf(x: str) -> bool:
        if not x or not isinstance(x, str):
            return False
        STATES = {'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}
        return x.upper() in STATES

    def _normalize_cep(c: str) -> Optional[str]:
        if not c: return None
        digits = re.sub(r'\D', '', c)
        if len(digits) == 8:
            return digits[:5] + '-' + digits[5:]
        return None

    def _plausible_municipio(m: str) -> bool:
        if not m or not isinstance(m, str): return False
        m = m.strip()
        if len(m) < 3 or len(m) > 60: return False
        # avoid common street prefixes
        if re.match(r'^(R\.?\s|Rua\b|Av\.?\b|Avenida\b|Rod\.?\b|Rodovia\b)', m, re.IGNORECASE):
            return False
        if not re.search(r'[A-Za-zÀ-ÿ]', m): return False
        return True

    def _plausible_bairro(b: str) -> bool:
        if not b or not isinstance(b, str): return False
        b = b.strip()
        if len(b) < 2 or len(b) > 60: return False
        if re.search(r'\d', b) and len(re.sub(r'\D', '', b)) > 4:
            return False
        return True

    # 1) Explicit CEP
    cep_m = re.search(r'(?:CEP[:\s]*|cep[:\s]*|\b)(\d{5}-?\d{3})\b', s)
    if cep_m:
        nc = _normalize_cep(cep_m.group(1))
        if nc:
            out['cep'] = nc
    else:
        m2 = re.search(r'(?<!\d)(\d{8})(?!\d)', s)
        if m2:
            nc = _normalize_cep(m2.group(1))
            if nc:
                out['cep'] = nc

    # 2) Bairro label (high confidence)
    b = re.search(r'Bairro[:\s-]*([^,\n]+)', s, re.IGNORECASE)
    if b and _plausible_bairro(b.group(1)):
        out['bairro'] = b.group(1).strip()

    # 3) UF detection
    uf_m = re.search(r'[-,]\s*([A-Za-z]{2})\b', s)
    if uf_m and _valid_uf(uf_m.group(1)):
        out['uf'] = uf_m.group(1).upper()
    else:
        uf_m2 = re.search(r'\b([A-Za-z]{2})\b\s*(?:,|$)', s)
        if uf_m2 and _valid_uf(uf_m2.group(1)):
            out['uf'] = uf_m2.group(1).upper()

    # 4) Municipio heuristics
    if out['uf']:
        mcity = re.search(r'([^,\-\n]+?)\s*[-,]\s*' + re.escape(out['uf']) + r'\b', s)
        if mcity and _plausible_municipio(mcity.group(1)):
            out['municipio'] = mcity.group(1).strip()

    if not out['municipio']:
        if out.get('cep'):
            parts = [p.strip() for p in s.split(',') if p.strip()]
            for i, part in enumerate(parts):
                if out['cep'].replace('-', '') in re.sub(r'\D', '', part):
                    if i-1 >= 0 and _plausible_municipio(parts[i-1]):
                        out['municipio'] = parts[i-1]
                        break
        if not out['municipio']:
            toks = [t.strip() for t in s.split(',') if t.strip()]
            if toks:
                cand = toks[-1]
                if _plausible_municipio(cand):
                    out['municipio'] = cand

    # 5) Bairro guess from token before municipio
    if not out['bairro'] and out.get('municipio'):
        parts = [p.strip() for p in s.split(',') if p.strip()]
        for i, p in enumerate(parts):
            if out['municipio'] and out['municipio'] in p:
                if i-1 >= 0 and _plausible_bairro(parts[i-1]):
                    out['bairro'] = parts[i-1]
                    break

    # 6) Last-resort bairro keywords
    if not out['bairro']:
        m3 = re.search(r'\b(Centro|Vila|Jardim|Parque|Residencial|Conjunto)\b[^,\n]*', s, re.IGNORECASE)
        if m3 and _plausible_bairro(m3.group(0)):
            out['bairro'] = m3.group(0).strip()

    for k in list(out.keys()):
        if out[k] and isinstance(out[k], str):
            out[k] = out[k].strip()

    return out


# shared regexes for item recovery
# Accepts numbers like:
#  - 420,00
#  - 1.234,56
#  - R$ 1.234,56
#  - 420
# Decimal cents are optional to account for some OCR outputs
_money_re = re.compile(r'R?\$?\s*([0-9]{1,3}(?:[\.,][0-9]{3})*(?:[\.,][0-9]{2,4}))')
_ncm_re = re.compile(r'(?<!\d)(\d{8})(?!\d)')
_cfop_re = re.compile(r'(?<!\d)(\d{4})(?!\d)')
# CST: 2 or 3 digits (00-99 or 000-999)
_cst_re = re.compile(r'(?:CST[:\s]*|CSOSN[:\s]*)(\d{2,3})(?!\d)', re.IGNORECASE)
# CSOSN: 3 digits (101, 102, 103, 201, 202, 203, 300, 400, 500, 900)
_csosn_re = re.compile(r'(?:CSOSN[:\s]*)([1-9]\d{2})(?!\d)', re.IGNORECASE)
# Quantity: prefer numbers with decimal or accompanied by unit markers (UN, KG, PC, LT)
_qty_re = re.compile(r'(\d+(?:[\.,]\d+)?)(?=\s*(?:x|X|UN\b|KG\b|PC\b|LT\b|UNID\b|UN\.\b)?)', re.IGNORECASE)


def _parse_money_token(tok: str) -> Optional[float]:
    """Parse a monetary token in Brazilian format and return float in BRL.

    Rules:
    - Accepts optional 'R$' prefix and whitespace
    - Thousands separator is '.' and decimal separator is ',' in Brazilian notation
    - Also accepts dot as decimal separator when OCR produced that (e.g., '420.00')
    - If both '.' and ',' appear, assume '.' are thousands and ',' is decimal
    - If only ',' appears, treat it as decimal separator
    - If only '.' appears, infer decimal vs thousands by checking fraction length
    - Returns float rounded to 2 decimals when successful
    """
    if not tok:
        return None
    s = re.sub(r'[^0-9,\.]', '', str(tok))
    if not s:
        return None
    try:
        # both separators present -> '.' thousands, ',' decimal
        if '.' in s and ',' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s and '.' not in s:
            s = s.replace(',', '.')
        elif '.' in s and ',' not in s:
            parts = s.split('.')
            # if it looks like a decimal with two fraction digits, keep it
            if len(parts) == 2 and len(parts[1]) == 2:
                s = s
            else:
                # treat dots as thousand separators
                s = s.replace('.', '')

        if s in ['', '-', ',', '.']:
            return None
        val = float(s)
        # Reject implausible huge values that are likely identifiers (CNPJ-like OCR artifacts)
        if val is not None and val > 10_000_000:
            return None
        # round to cents to avoid floating representations like 420.0000001
        return round(val, 2)
    except Exception:
        return None


def _find_product_section_lines(text: str) -> List[str]:
    markers = [r'DADOS DO PRODUTO', r'DADOS DO PRODUTO/SERVI\xC3\x87O', r'DESCRI\xC3\x87\xC3\x83O DOS PRODUTOS', r'DADOS DO PRODUTO']
    low = text
    for m in markers:
        i = low.find(m)
        if i != -1:
            lines = low[i:].splitlines()
            return [l.strip() for l in lines[1:41] if l.strip()]
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-80:]


def _extract_codes_with_llm(text: str) -> Dict[str, Optional[str]]:
    """Extract fiscal codes using LLM first, then regex fallback."""
    codes = {'ncm': None, 'cfop': None, 'cst': None, 'csosn': None}
    
    # Try LLM for each code
    try:
        from . import llm_helper
        for code_name in codes.keys():
            result = llm_helper.extract_field_with_llm(code_name, text)
            if result.get('ok') and result.get('value') and result.get('confidence', 0) >= 0.6:
                codes[code_name] = result.get('value')
    except Exception:
        pass
    
    # Fallback to regex for any missing codes
    if not codes.get('ncm'):
        m = _ncm_re.search(text)
        if m:
            codes['ncm'] = m.group(1)
    
    if not codes.get('cfop'):
        m = _cfop_re.search(text)
        if m:
            codes['cfop'] = m.group(1)
    
    if not codes.get('cst'):
        m = _cst_re.search(text)
        if m:
            codes['cst'] = m.group(1)
    
    if not codes.get('csosn'):
        m = _csosn_re.search(text)
        if m:
            codes['csosn'] = m.group(1)
    
    return codes


def _extract_items_with_llm(text: str) -> List[Dict[str, Any]]:
    """Extract items using LLM first, then heuristic fallback."""
    try:
        from . import llm_helper
        result = llm_helper.extract_items_with_llm(text)
        if result.get('ok') and result.get('items') and result.get('confidence', 0) >= 0.6:
            items = result.get('items', [])
            # Normalize LLM items to our schema
            normalized_items = []
            for item in items:
                if isinstance(item, dict):
                    normalized = {
                        'descricao': item.get('descricao'),
                        'quantidade': item.get('quantidade'),
                        'unidade': item.get('unidade'),
                        'valor_unitario': item.get('valor_unitario'),
                        'valor_total': item.get('valor_total'),
                        'codigo': item.get('codigo'),
                        'ncm': item.get('ncm'),
                        'cfop': item.get('cfop'),
                        'cst': item.get('cst')
                    }
                    normalized_items.append(normalized)
            if normalized_items:
                return normalized_items
    except Exception:
        pass
    
    # Fallback to heuristic extraction
    lines = _find_product_section_lines(text)
    return _extract_items_from_lines(lines)


def _extract_items_from_lines(lines: List[str]) -> List[Dict[str, Any]]:
    items = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        ncm = _ncm_re.search(ln)
        # skip lines that are clearly weight/transport headers (avoid parsing peso as item value)
        if re.search(r'PESO|PESO BRUTO|PESO L[IÍ]QUIDO|TRANSPORTADOR|FRETE', ln, re.IGNORECASE):
            i += 1
            continue
        money = _money_re.search(ln)
        cfop = _cfop_re.search(ln)
        
        # Look for item patterns - improved detection for multiple items
        if money and (ncm or cfop or re.search(r'\d+[\.,]\d{2}', ln)):
            desc = re.sub(r'\b' + (ncm.group(1) if ncm else '') + r'\b', '', ln) if ncm else ln
            desc = re.sub(r'\s{2,}', ' ', desc).strip()
            if len(desc) < 5 and i > 0:
                desc = lines[i-1]
            qty = None
            # find quantity only if it appears with unit markers or looks like a decimal count
            qm = re.search(r'(\d+(?:[\.,]\d+)?)(?=\s*(?:x|X|UN\b|KG\b|PC\b|LT\b|UNID\b|UN\.\b))', ln, re.IGNORECASE)
            if not qm:
                if i>0:
                    qm = _qty_re.search(lines[i-1])
            if qm:
                qty = qm.group(1)
            val_tok = money.group(1)
            val = _parse_money_token(val_tok)
            if val is None:
                if i+1 < len(lines):
                    m2 = _money_re.search(lines[i+1])
                    if m2:
                        val = _parse_money_token(m2.group(1))
            item = {
                'descricao': desc[:200] if desc else None,
                'quantidade': qty,
                'unidade': None,
                'valor_unitario': val,
                'valor_total': val,
                'codigo': None,
                'ncm': ncm.group(1) if ncm else None,
                'cfop': cfop.group(1) if cfop else None,
                'cst': None
            }
            items.append(item)
            i += 1
            continue
            
        # Also look for lines with product codes (common in Leroy Merlin format)
        codigo_match = re.search(r'^(\d{6,8})\s+(.+)', ln)
        if codigo_match and i+1 < len(lines):
            codigo = codigo_match.group(1)
            desc_part1 = codigo_match.group(2)
            # Look ahead for value information
            next_line = lines[i+1]
            money_next = _money_re.search(next_line)
            if money_next:
                # Combine description from current and next line if needed
                desc = desc_part1
                if not money_next.group(1) in desc_part1:  # Description doesn't contain the price
                    desc_parts = next_line.split()
                    for part in desc_parts:
                        if not re.search(r'\d+[\.,]\d{2}', part):
                            desc += ' ' + part
                
                val = _parse_money_token(money_next.group(1))
                if val is not None:
                    item = {
                        'descricao': desc[:200] if desc else None,
                        'quantidade': None,
                        'unidade': None,
                        'valor_unitario': val,
                        'valor_total': val,
                        'codigo': codigo,
                        'ncm': None,
                        'cfop': None,
                        'cst': None
                    }
                    items.append(item)
                    i += 2  # Skip next line as we processed it
                    continue
        
        if _money_re.search(ln) and i>0:
            prev = lines[i-1]
            # avoid using a prev line that is numeric-only (CNPJ, peso, codes)
            if not re.search(r'[A-Za-zÀ-ÿ]', prev):
                # previous line has no letters -> likely not a description
                i += 1
                continue
            val = _parse_money_token(_money_re.search(ln).group(1))
            if val is not None and val <= 10000000 and len(prev) > 3:
                # also avoid prev that looks like a CNPJ/CPF
                if re.search(r'\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/]?\d{4}[-\s]?\d{2}|\d{14}', prev):
                    i += 1
                    continue
                item = {
                    'descricao': prev[:200],
                    'quantidade': None,
                    'unidade': None,
                    'valor_unitario': val,
                    'valor_total': val,
                    'codigo': None,
                    'ncm': None,
                    'cfop': None,
                    'cst': None
                }
                items.append(item)
        i += 1
    return items


def refine_extracted(record: Dict[str, Any], extracted: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Attempt to improve extracted dict by finding missing items, descriptions and codes.
    Now uses LLM-first approach before falling back to regex.

    Returns (updated_extracted, notes)
    notes contains 'filled' dict similar to enrichment_agent.report['filled'] and 'notes' list.
    """
    notes = {'filled': {}, 'notes': []}
    text = _text_sources(record)

    # ensure extracted structure
    if not isinstance(extracted, dict):
        extracted = {}

    # ITEMS recovery - LLM first
    try:
        existing_items = extracted.get('itens') if isinstance(extracted.get('itens'), list) else []
        
        # Try LLM extraction first
        llm_items = _extract_items_with_llm(text)
        
        if existing_items:
            # Merge LLM items with existing items
            for idx, it in enumerate(existing_items):
                if not it.get('descricao') and idx < len(llm_items):
                    it['descricao'] = llm_items[idx].get('descricao')
                    notes['filled'][f'itens[{idx}].descricao'] = it['descricao']
                    notes['notes'].append(f'LLM extracted descricao for item {idx}')
                try:
                    if (it.get('valor_unitario') is None or (isinstance(it.get('valor_unitario'), (int,float)) and it.get('valor_unitario')>1e6)) and llm_items[idx].get('valor_unitario'):
                        it['valor_unitario'] = llm_items[idx].get('valor_unitario')
                        notes['filled'][f'itens[{idx}].valor_unitario'] = it['valor_unitario']
                        notes['notes'].append(f'LLM extracted valor_unitario for item {idx}')
                    if (it.get('valor_total') is None or (isinstance(it.get('valor_total'), (int,float)) and it.get('valor_total')>1e6)) and llm_items[idx].get('valor_total'):
                        it['valor_total'] = llm_items[idx].get('valor_total')
                        notes['filled'][f'itens[{idx}].valor_total'] = it['valor_total']
                        notes['notes'].append(f'LLM extracted valor_total for item {idx}')
                except Exception:
                    pass
            extracted['itens'] = existing_items
        else:
            if llm_items:
                extracted['itens'] = llm_items
                notes['filled']['itens'] = llm_items
                notes['notes'].append(f'LLM extracted {len(llm_items)} items')

        # Extract fiscal codes using LLM first
        cf = extracted.get('codigos_fiscais') if isinstance(extracted.get('codigos_fiscais'), dict) else {}
        llm_codes = _extract_codes_with_llm(text)
        
        for code_name, code_value in llm_codes.items():
            if code_value and not cf.get(code_name):
                cf[code_name] = code_value
                notes['filled'][f'codigos_fiscais.{code_name}'] = code_value
                notes['notes'].append(f'LLM extracted {code_name}: {code_value}')
        
        if cf:
            extracted['codigos_fiscais'] = cf

    except Exception as e:
        notes['notes'].append(f'LLM items/codes extraction failed: {e}, falling back to regex')
        
        # Fallback to original regex-based extraction
        existing_items = extracted.get('itens') if isinstance(extracted.get('itens'), list) else []
        recovered = []
        lines = _find_product_section_lines(text)
        cand = _extract_items_from_lines(lines)
        if existing_items:
            for idx, it in enumerate(existing_items):
                if not it.get('descricao') and idx < len(cand):
                    it['descricao'] = cand[idx].get('descricao')
                    notes['filled'][f'itens[{idx}].descricao'] = it['descricao']
                try:
                    if (it.get('valor_unitario') is None or (isinstance(it.get('valor_unitario'), (int,float)) and it.get('valor_unitario')>1e6)) and cand[idx].get('valor_unitario'):
                        it['valor_unitario'] = cand[idx].get('valor_unitario')
                        notes['filled'][f'itens[{idx}].valor_unitario'] = it['valor_unitario']
                    if (it.get('valor_total') is None or (isinstance(it.get('valor_total'), (int,float)) and it.get('valor_total')>1e6)) and cand[idx].get('valor_total'):
                        it['valor_total'] = cand[idx].get('valor_total')
                        notes['filled'][f'itens[{idx}].valor_total'] = it['valor_total']
                except Exception:
                    pass
            extracted['itens'] = existing_items
        else:
            if cand:
                extracted['itens'] = cand
                notes['filled']['itens'] = cand

        # Fallback regex extraction for codes
        cf = extracted.get('codigos_fiscais') if isinstance(extracted.get('codigos_fiscais'), dict) else {}
        if not cf.get('ncm'):
            m = _ncm_re.search(text)
            if m:
                cf['ncm'] = m.group(1)
                notes['filled']['codigos_fiscais.ncm'] = cf['ncm']
        if not cf.get('cfop'):
            m2 = _cfop_re.search(text)
            if m2:
                cf['cfop'] = m2.group(1)
                notes['filled']['codigos_fiscais.cfop'] = cf['cfop']
        if not cf.get('cst'):
            m3 = _cst_re.search(text)
            if m3:
                cf['cst'] = m3.group(1)
                notes['filled']['codigos_fiscais.cst'] = cf['cst']
        if not cf.get('csosn'):
            m4 = _csosn_re.search(text)
            if m4:
                cf['csosn'] = m4.group(1)
                notes['filled']['codigos_fiscais.csosn'] = cf['csosn']
        if cf:
            extracted['codigos_fiscais'] = cf

    # PARTY names alternatives
    try:
        m = re.search(r'DESTINAT[ÁA]RIO\s*/\s*REMETENTE\s*\n(.*?)\n', text, re.IGNORECASE|re.DOTALL)
        if m:
            cand = m.group(1).strip()
            if cand and not extracted.get('destinatario', {}).get('razao_social'):
                extracted.setdefault('destinatario', {})
                extracted['destinatario']['razao_social'] = cand.split('\n')[0]
                notes['filled']['destinatario.razao_social'] = extracted['destinatario']['razao_social']
    except Exception:
        pass

    # Attempt to parse address components (bairro, municipio, uf, cep) from any present endereco fields
    try:
        for party in ('emitente', 'destinatario'):
            if not isinstance(extracted.get(party), dict):
                continue
            addr = extracted[party].get('endereco') or ''
            if addr and isinstance(addr, str) and addr.strip():
                parts = _extract_address_parts(addr)
                if parts.get('cep') and not extracted[party].get('cep'):
                    extracted[party]['cep'] = parts.get('cep')
                    notes['filled'][f'{party}.cep'] = parts.get('cep')
                if parts.get('uf') and not extracted[party].get('uf'):
                    extracted[party]['uf'] = parts.get('uf')
                    notes['filled'][f'{party}.uf'] = parts.get('uf')
                if parts.get('municipio') and not extracted[party].get('municipio'):
                    extracted[party]['municipio'] = parts.get('municipio')
                    notes['filled'][f'{party}.municipio'] = parts.get('municipio')
                if parts.get('bairro') and not extracted[party].get('bairro'):
                    extracted[party]['bairro'] = parts.get('bairro')
                    notes['filled'][f'{party}.bairro'] = parts.get('bairro')
            else:
                m2 = re.search(fr'{party.upper()}[:\s\-\n]{{0,10}}([\s\S]{{0,200}}?)\n', text, re.IGNORECASE)
                if m2:
                    cand_addr = m2.group(1).strip()
                    parts = _extract_address_parts(cand_addr)
                    if parts.get('cep') and not extracted[party].get('cep'):
                        extracted[party]['cep'] = parts.get('cep')
                        notes['filled'][f'{party}.cep'] = parts.get('cep')
                    if parts.get('uf') and not extracted[party].get('uf'):
                        extracted[party]['uf'] = parts.get('uf')
                        notes['filled'][f'{party}.uf'] = parts.get('uf')
                    if parts.get('municipio') and not extracted[party].get('municipio'):
                        extracted[party]['municipio'] = parts.get('municipio')
                        notes['filled'][f'{party}.municipio'] = parts.get('municipio')
                    if parts.get('bairro') and not extracted[party].get('bairro'):
                        extracted[party]['bairro'] = parts.get('bairro')
                        notes['filled'][f'{party}.bairro'] = parts.get('bairro')
    except Exception:
        pass

    return extracted, notes
