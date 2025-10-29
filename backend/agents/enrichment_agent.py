"""
Enrichment agent: heuristics to locate missing fiscal fields in OCR/raw extracted text.

Provides:
- enrich_record(record): returns (updated_extracted_dict, report)
- compute_aggregates(extracted): same semantics as main.compute_aggregates (minimal duplicate)

This module intentionally avoids importing main to prevent circular imports.
"""
import re
import json
from typing import Tuple, Dict, Any, Optional

try:
    from . import specialist_agent
except Exception:
    specialist_agent = None


def _to_text_sources(record: Dict[str, Any]) -> str:
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


def find_cnpj(text: str) -> Optional[str]:
    if not text:
        return None
    # common formats: 00.000.000/0000-00 or only digits (14)
    # accept common punctuation and also spaced variants
    m = re.search(r'(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2})', text)
    if m:
        return re.sub(r'\D', '', m.group(1))
    m2 = re.search(r'(?<!\d)(\d{14})(?!\d)', text)
    if m2:
        return m2.group(1)
    return None


def find_chave(text: str) -> Optional[str]:
    if not text:
        return None
    # chave de acesso NF-e: 44 digits
    # Accept sequences of 44 digits possibly separated by spaces or non-digit chars
    m = re.search(r'(?:(?:\d\D?){44})', text)
    if m:
        digits = re.sub(r'\D', '', m.group(0))
        if len(digits) == 44:
            return digits
    # fallback strict
    m2 = re.search(r'(?<!\d)(\d{44})(?!\d)', text)
    if m2:
        return m2.group(1)
    if m:
        return m
    return None


def find_date(text: str) -> Optional[str]:
    if not text:
        return None
    # dd/mm/yyyy or yyyy-mm-dd
    m = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m:
        d = m.group(1)
        dd, mm, yyyy = d.split('/')
        return f"{yyyy}-{mm}-{dd}"
    m2 = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m2:
        return m2.group(1)
    return None


def find_numero_nota(text: str) -> Optional[str]:
    if not text:
        return None
    # look for patterns like Nº 1234, N: 1234, 'Nota 1234', 'NF 1234'
    m = re.search(r'(?:n\s*[ºo]?\s*[:\-]?|nota\s*[:\-]?|nf\s*[:\-]?|n[:\-]\s*)(\d{1,10})', text, re.IGNORECASE)
    if m:
        return m.group(1)
    # fallback: standalone small numbers near words 'numero' or 'n:'
    m2 = re.search(r'numero\s*(\d{1,10})', text, re.IGNORECASE)
    if m2:
        return m2.group(1)
    return None


def find_natureza_operacao(text: str) -> Optional[str]:
    """Extract natureza da operacao - LLM first, then regex fallback."""
    if not text:
        return None
    
    # Try LLM first
    try:
        from . import llm_helper
        result = llm_helper.extract_field_with_llm('natureza_operacao', text)
        if result.get('ok') and result.get('value') and result.get('confidence', 0) >= 0.6:
            return result.get('value')
    except Exception:
        pass
    
    # Fallback to regex if LLM fails or confidence too low
    # Common patterns: "NATUREZA DA OPERAÇÃO: VENDA"
    m = re.search(r'NATUREZA\s+DA\s+OPERA[CÇ][AÃ]O\s*[:\-]?\s*([A-ZÀ-Ú\s]{3,60})', text, re.IGNORECASE)
    if m:
        nat = m.group(1).strip()
        # clean up common noise
        nat = re.sub(r'\s{2,}', ' ', nat)
        if len(nat) > 3 and len(nat) < 60:
            return nat
    # Fallback: look for common operations
    common = ['VENDA', 'COMPRA', 'TRANSFERENCIA', 'DEVOLUCAO', 'REMESSA', 'RETORNO']
    for op in common:
        if re.search(r'\b' + op + r'\b', text, re.IGNORECASE):
            return op
    return None


def find_forma_pagamento(text: str) -> Optional[str]:
    """Extract forma de pagamento - LLM first, then regex fallback."""
    if not text:
        return None
    
    # Try LLM first
    try:
        from . import llm_helper
        result = llm_helper.extract_field_with_llm('forma_pagamento', text)
        if result.get('ok') and result.get('value') and result.get('confidence', 0) >= 0.6:
            return result.get('value')
    except Exception:
        pass
    
    # Fallback to regex if LLM fails or confidence too low
    # Common patterns: "FORMA DE PAGAMENTO: DINHEIRO"
    m = re.search(r'FORMA\s+DE\s+PAGAMENTO\s*[:\-]?\s*([A-ZÀ-Ú\s]{3,40})', text, re.IGNORECASE)
    if m:
        forma = m.group(1).strip()
        forma = re.sub(r'\s{2,}', ' ', forma)
        if len(forma) > 2 and len(forma) < 40:
            return forma
    # Fallback: look for common payment methods
    common = {
        r'\bDINHEIRO\b': 'DINHEIRO',
        r'\bCARTAO\b|\bCARTÃO\b': 'CARTAO',
        r'\bBOLETO\b': 'BOLETO',
        r'\bPIX\b': 'PIX',
        r'\bCHEQUE\b': 'CHEQUE',
        r'\bCREDITO\b|\bCRÉDITO\b': 'CREDITO',
        r'\bDEBITO\b|\bDÉBITO\b': 'DEBITO',
        r'\bA\s+VISTA\b|\bAVISTA\b|\bÀ\s+VISTA\b': 'A VISTA',
        r'\bA\s+PRAZO\b|\bAPRAZO\b': 'A PRAZO'
    }
    for pattern, value in common.items():
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return None


def find_aliquota_icms(text: str) -> Optional[float]:
    """Extract ICMS aliquota - LLM first, then regex fallback."""
    if not text:
        return None
    
    # Try LLM first
    try:
        from . import llm_helper
        result = llm_helper.extract_field_with_llm('aliquota_icms', text)
        if result.get('ok') and result.get('value') is not None and result.get('confidence', 0) >= 0.6:
            try:
                return float(result.get('value'))
            except Exception:
                pass
    except Exception:
        pass
    
    # Fallback to regex if LLM fails or confidence too low
    # Pattern: "ALIQ ICMS: 18%" or "ALIQUOTA ICMS 18,00%"
    m = re.search(r'AL[IÍ]Q(?:UOTA)?\s+(?:DO\s+)?ICMS\s*[:\-]?\s*([0-9]+[\.,]?[0-9]*)\s*%?', text, re.IGNORECASE)
    if m:
        try:
            val = m.group(1).replace(',', '.')
            return float(val)
        except Exception:
            pass
    return None


def find_valor_total_impostos(text: str) -> Optional[float]:
    """Extract total tax value from text. Looks for patterns like 'Vlr Aprox dos Tributos: R$ 56,49 Federal / R$ 50,40 Estadual'."""
    if not text:
        return None
    
    # Look for the specific pattern from Brazilian fiscal documents
    pattern = r'(?:vlr\s+aprox\s+dos\s+tributos|valor\s+aprox\s+tributos|tributos)[:\s]*(?:r\$\s*)?([0-9]+[,\.][0-9]{2})\s*federal\s*[/]\s*(?:r\$\s*)?([0-9]+[,\.][0-9]{2})\s*estadual'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            federal = float(m.group(1).replace(',', '.'))
            estadual = float(m.group(2).replace(',', '.'))
            return federal + estadual
        except Exception:
            pass
    
    # Alternative pattern: just look for "tributos" with a single value
    pattern2 = r'(?:vlr\s+aprox\s+dos\s+tributos|valor.*tributos)[:\s]*(?:r\$\s*)?([0-9]+[,\.][0-9]{2})'
    m2 = re.search(pattern2, text, re.IGNORECASE)
    if m2:
        try:
            return float(m2.group(1).replace(',', '.'))
        except Exception:
            pass
    
    return None


def find_money(text: str) -> Optional[float]:
    if not text:
        return None
    
    # PRIORITY 1: Find explicit "VALOR TOTAL DA NOTA" patterns first
    valor_total_nota_re = re.compile(r'valor\s+total\s+da\s+nota[:\s]*(?:r\$\s*)?([0-9]+[\.,][0-9]{2})', re.IGNORECASE)
    m_nota = valor_total_nota_re.search(text)
    if m_nota:
        s = m_nota.group(1).replace('.', '').replace(',', '.')
        try:
            val = float(s)
            if val > 0 and val < 10_000_000:
                return val
        except Exception:
            pass
    
    # PRIORITY 2: find currency-like values, prefer lines with 'total'
    currency_re = re.compile(r'(?:valor\s+total|total.*nota|total)\s*[:\-]?\s*R?\$?\s*([0-9]+[\.,][0-9]{2})', re.IGNORECASE)
    m = currency_re.search(text)
    if m:
        s = m.group(1).replace('.', '').replace(',', '.')
        try:
            val = float(s)
            # Reject implausible values that are likely identifiers (CNPJ-like numbers)
            if val > 10_000_000:
                pass
            else:
                return val
        except Exception:
            pass

    # PRIORITY 3: Look for explicit currency symbols
    any_money_re = re.compile(r'R\$\s*([0-9]+[\.,][0-9]{2})')
    m2 = any_money_re.search(text)
    if m2:
        s = m2.group(1).replace('.', '').replace(',', '.')
        try:
            val = float(s)
            # Reject implausible values that are likely identifiers
            if val > 10_000_000:
                pass
            else:
                return val
        except Exception:
            pass

    # PRIORITY 4: last resort: find decimal numbers, but be very careful to avoid CNPJ/CPF/identifiers
    decimal_numbers = re.findall(r'([0-9]{1,3}(?:\.[0-9]{3})*[,][0-9]{2})', text)
    if decimal_numbers:
        # Prefer the last decimal number that looks like currency (Brazilian format)
        for cand in reversed(decimal_numbers):
            # Check context around this number
            span_index = text.rfind(cand)
            context_before = text[max(0, span_index-30): span_index]
            context_after = text[span_index+len(cand): span_index+len(cand)+30]
            full_context = context_before + cand + context_after
            
            # Skip if context suggests it's an identifier
            if any(keyword in full_context.lower() for keyword in ['cnpj', 'cpf', 'inscr', 'codigo', 'chave']):
                continue
            
            # Skip if surrounded by identifier-like patterns
            if '/' in full_context or '-' in context_after:
                continue
                
            # Convert and validate
            s = cand.replace('.', '').replace(',', '.')
            try:
                val = float(s)
                # Reject extremely large values that are likely identifiers
                if val > 10_000_000:
                    continue
                return val
            except Exception:
                continue
    
    return None


def find_total_impostos(text: str) -> Optional[float]:
    """Extract total tax value from fiscal document text."""
    if not text:
        return None
    
    # Look for explicit tax total patterns (Brazilian format)
    tax_patterns = [
        r'(?:vlr\s+aprox\s+dos\s+tributos?|valor\s+aproximado\s+dos\s+tributos?|total\s+tributos?)\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'(?:impostos?\s+totais?|total\s+de\s+impostos?)\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+(?:federal|estadual|municipal)'
    ]
    
    for pattern in tax_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Get the first valid tax value
            for match in matches:
                try:
                    s = match.replace('.', '').replace(',', '.')
                    val = float(s)
                    if 0 < val < 100000:  # Reasonable tax value range
                        return val
                except Exception:
                    continue
    
    # Look for individual tax components to sum
    tax_components = []
    individual_patterns = [
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+federal',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+estadual',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+municipal',
        r'icms\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'ipi\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'pis\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'cofins\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})'
    ]
    
    for pattern in individual_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                s = match.replace('.', '').replace(',', '.')
                val = float(s)
                if 0 < val < 100000:
                    tax_components.append(val)
            except Exception:
                continue
    
    # Return sum of individual components if found
    if tax_components:
        return sum(tax_components)
    
    return None


def _deep_scan_for_key(data, key_candidates):
    """Recursively scan a nested dict/list for any string value that contains any of the key_candidates labels (case-insensitive) and return the value found.
    Useful for digging address/chave values inside nested LLM outputs.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                if any(ck in str(k).lower() for ck in key_candidates) and isinstance(v, (str, int, float)):
                    sval = str(v)
                    # avoid returning huge JSON blobs or serialized dicts
                    if len(sval) > 200 or (sval.strip().startswith('{') and sval.strip().endswith('}')):
                        # skip overly large/JSON-like values
                        pass
                    else:
                        return sval
            except Exception:
                pass
            # recurse
            res = _deep_scan_for_key(v, key_candidates)
            if res:
                return res
    elif isinstance(data, list):
        for el in data:
            res = _deep_scan_for_key(el, key_candidates)
            if res:
                return res
    return None


def compute_aggregates(extracted: Dict[str, Any]) -> Dict[str, Any]:
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

    # compute top-level and items sum, prefer items sum when reliable
    vt = None
    if isinstance(extracted, dict):
        top_vt = to_num(extracted.get('valor_total'))
        items = (extracted.get('itens') or [])
        sum_items = 0.0
        items_count = 0
        for it in items:
            v = to_num(it.get('valor_total')) if isinstance(it, dict) else None
            if v is not None:
                sum_items += v
                items_count += 1

        if items_count > 0 and sum_items > 0:
            if top_vt is None or abs(sum_items - top_vt) > 0.5:
                vt = sum_items
            else:
                vt = top_vt
        else:
            vt = top_vt

    impostos = (extracted.get('impostos') or {}) if isinstance(extracted, dict) else {}
    icms = to_num((impostos.get('icms') or {}).get('valor') if isinstance(impostos.get('icms'), dict) else impostos.get('icms')) or 0.0
    ipi = to_num((impostos.get('ipi') or {}).get('valor') if isinstance(impostos.get('ipi'), dict) else impostos.get('ipi')) or 0.0
    pis = to_num((impostos.get('pis') or {}).get('valor') if isinstance(impostos.get('pis'), dict) else impostos.get('pis')) or 0.0
    cofins = to_num((impostos.get('cofins') or {}).get('valor') if isinstance(impostos.get('cofins'), dict) else impostos.get('cofins')) or 0.0

    return {
        'valor_total_calc': vt if vt is not None else 0.0,
        'impostos_calc': {'icms': icms, 'ipi': ipi, 'pis': pis, 'cofins': cofins}
    }


def enrich_record(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Try to fill missing/null extracted fields using heuristics on available text.

    Returns (new_extracted_dict, report) where report contains fields filled and confidence notes.
    """
    report = {'filled': {}, 'notes': []}

    # Prepare base extracted data
    extracted = {}
    if record.get('extracted_data') and isinstance(record.get('extracted_data'), dict):
        extracted = dict(record.get('extracted_data'))
    else:
        extracted = {}

    text = _to_text_sources(record)

    # Deep-scan raw_extracted JSON (if present) for address-like keys and chave
    raw = record.get('raw_extracted')
    try:
        if raw:
            # common labels
            addr_candidate = _deep_scan_for_key(raw, ['endereco', 'endereço', 'address', 'logradouro', 'endereco de entrega'])
            if addr_candidate and not extracted['emitente'].get('endereco'):
                extracted['emitente']['endereco'] = addr_candidate
                report['filled']['emitente.endereco'] = addr_candidate
            chave_candidate = _deep_scan_for_key(raw, ['chave', 'chave_acesso', 'nfe', 'chave de acesso'])
            if chave_candidate and not extracted.get('chave_acesso'):
                digits = re.sub(r'\D', '', chave_candidate)
                if len(digits) == 44:
                    extracted['chave_acesso'] = digits
                    report['filled']['chave_acesso'] = digits
    except Exception:
        pass

    # --- party: emitente / destinatario
    if 'emitente' not in extracted or not isinstance(extracted.get('emitente'), dict):
        extracted['emitente'] = {'razao_social': None, 'cnpj': None, 'inscricao_estadual': None, 'endereco': None}
    if 'destinatario' not in extracted or not isinstance(extracted.get('destinatario'), dict):
        extracted['destinatario'] = {'razao_social': None, 'cnpj': None, 'inscricao_estadual': None, 'endereco': None}

    # Try to find CNPJ for emitente if missing
    if not extracted['emitente'].get('cnpj'):
        c = find_cnpj(text)
        if c:
            extracted['emitente']['cnpj'] = c
            report['filled']['emitente.cnpj'] = c

    # Extract valor_total_impostos
    if not extracted.get('valor_total_impostos'):
        imp = find_total_impostos(text)
        if imp is not None:
            extracted['valor_total_impostos'] = imp
            report['filled']['valor_total_impostos'] = imp

    # Try deeper OCR scanning for address lines if endereco missing
    if not extracted['emitente'].get('endereco') and text:
        try:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i, ln in enumerate(lines):
                if re.search(r'ENDEREC[OÕ]|ENDERE[CÇ]O|LOGRADOURO|AV\.|RUA|AVENIDA', ln, re.IGNORECASE):
                    # take this line and a following token as address
                    cand = ln
                    if i+1 < len(lines):
                        cand2 = lines[i+1]
                        # join if next contains digits or CEP
                        if re.search(r'\d', cand2) or re.search(r'CEP', cand2, re.IGNORECASE):
                            cand = cand + ' ' + cand2
                    extracted['emitente']['endereco'] = cand
                    report['filled']['emitente.endereco'] = cand
                    break
        except Exception:
            pass

    # Try to find CNPJ for destinatario if missing (rare), search for second occurrence
    if not extracted['destinatario'].get('cnpj'):
        # locate all cnpjs and pick second if exists
        all_cnpjs = re.findall(r'(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})', text)
        if len(all_cnpjs) >= 2:
            cand = re.sub(r'\D', '', all_cnpjs[1])
            extracted['destinatario']['cnpj'] = cand
            report['filled']['destinatario.cnpj'] = cand

    # razao_social heuristics: try first non-empty line if missing
    if not extracted['emitente'].get('razao_social'):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines:
            # pick first reasonably long line
            for ln in lines[:8]:
                if len(ln) > 4 and not re.search(r'\d', ln):
                    extracted['emitente']['razao_social'] = ln
                    report['filled']['emitente.razao_social'] = ln
                    break

    # --- top-level fields
    if not extracted.get('chave_acesso'):
        ch = find_chave(text)
        if ch:
            extracted['chave_acesso'] = ch
            report['filled']['chave_acesso'] = ch

    if not extracted.get('numero_nota'):
        n = find_numero_nota(text)
        if n:
            extracted['numero_nota'] = n
            report['filled']['numero_nota'] = n

    if not extracted.get('data_emissao'):
        d = find_date(text)
        if d:
            extracted['data_emissao'] = d
            report['filled']['data_emissao'] = d

    if not extracted.get('valor_total'):
        v = find_money(text)
        if v is not None:
            extracted['valor_total'] = v
            report['filled']['valor_total'] = v

    if not extracted.get('valor_total_impostos'):
        vti = find_valor_total_impostos(text)
        if vti is not None:
            extracted['valor_total_impostos'] = vti
            report['filled']['valor_total_impostos'] = vti

    if not extracted.get('natureza_operacao'):
        nat = find_natureza_operacao(text)
        if nat:
            extracted['natureza_operacao'] = nat
            report['filled']['natureza_operacao'] = nat

    if not extracted.get('forma_pagamento'):
        forma = find_forma_pagamento(text)
        if forma:
            extracted['forma_pagamento'] = forma
            report['filled']['forma_pagamento'] = forma

    # itens: if empty and we can find simple lines with currency, add a single inferred item
    if not extracted.get('itens'):
        # look for lines with description followed by money in next line
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        any_money_re = re.compile(r'R?\$\s*([0-9]+[\.,][0-9]{2})')
        candidate_item = None
        for i, ln in enumerate(lines[:-1]):
            if any_money_re.search(lines[i+1]):
                amt = any_money_re.search(lines[i+1]).group(1).replace('.', '').replace(',', '.')
                try:
                    val = float(amt)
                    candidate_item = {'descricao': ln[:200], 'quantidade': None, 'unidade': None, 'valor_unitario': val, 'valor_total': val}
                    break
                except Exception:
                    continue
        if candidate_item:
            extracted['itens'] = [candidate_item]
            report['filled']['itens'] = candidate_item

    # impostos: try to find explicit tax values if missing
    if not extracted.get('impostos'):
        extracted['impostos'] = {'icms': {'aliquota': None, 'base_calculo': None, 'valor': None}, 'ipi': {'valor': None}, 'pis': {'valor': None}, 'cofins': {'valor': None}}

    # quick search for 'ICMS' value
    try:
        if not (extracted.get('impostos') or {}).get('icms', {}).get('valor'):
            m = re.search(r'ICMS\s*[:\-]?\s*R?\$?\s*([0-9]+[\.,][0-9]{2})', text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1).replace('.', '').replace(',', '.'))
                    extracted['impostos']['icms']['valor'] = v
                    report['filled']['impostos.icms.valor'] = v
                except Exception:
                    pass
        # try to find ICMS aliquota
        if not (extracted.get('impostos') or {}).get('icms', {}).get('aliquota'):
            aliq = find_aliquota_icms(text)
            if aliq is not None:
                extracted['impostos']['icms']['aliquota'] = aliq
                report['filled']['impostos.icms.aliquota'] = aliq
    except Exception:
        pass

    # compute aggregates
    try:
        ag = compute_aggregates(extracted)
    except Exception:
        ag = {'valor_total_calc': None, 'impostos_calc': {'icms': 0.0, 'ipi': 0.0, 'pis': 0.0, 'cofins': 0.0}}

    # If we computed a total from items (ag['valor_total_calc']) and it disagrees with
    # the top-level 'valor_total' parsed from LLM/OCR, prefer the computed sum from items
    # when it seems more reliable (non-zero and difference notable). This avoids cases
    # where LLM parsed a wrong total while items are clearly present.
    try:
        computed = ag.get('valor_total_calc')
        def to_num_local(x):
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

        top = to_num_local(extracted.get('valor_total'))
        # PREFER EXPLICIT VALUES FROM OCR/LLM over calculated sums
        # Only use calculated value if no explicit value was found
        if top is not None and top > 0:
            # Keep the explicit value from OCR/LLM - it's more reliable than calculations
            ag['valor_total_calc'] = top
            report['notes'].append(f"Using explicit valor_total={top} from OCR/LLM (computed sum was {computed})")
        elif computed is not None and computed > 0:
            # Only use computed sum as fallback when no explicit value found
            extracted['valor_total'] = computed
            report['filled']['valor_total'] = computed
            report['notes'].append(f"Using computed valor_total={computed} (no explicit value found)")
            ag['valor_total_calc'] = computed
    except Exception:
        pass

    # run specialist agent if available to further refine items and codes
    if specialist_agent:
        try:
            refined, notes = specialist_agent.refine_extracted(record, extracted)
            # merge refined into extracted
            if isinstance(refined, dict):
                extracted = refined
            # merge notes into report
            try:
                if isinstance(notes, dict):
                    for k, v in (notes.get('filled') or {}).items():
                        report['filled'][k] = v
                    if notes.get('notes'):
                        report['notes'].extend(notes.get('notes'))
            except Exception:
                pass
            # recompute aggregates after specialist changes
            try:
                ag = compute_aggregates(extracted)
            except Exception:
                pass
        except Exception:
            report['notes'].append('specialist_agent failed')
    
    # After specialist modifications we may have new/updated items; if the recomputed
    # total now differs from the top-level valor_total, prefer the LLM top-level if
    # it was produced by the LLM. Otherwise, ask the LLM to re-verify before using
    # the computed sum. If no LLM key is configured, fall back to computed sum.
    try:
        computed_after = ag.get('valor_total_calc') if isinstance(ag, dict) else None
        top_after = None
        try:
            if extracted.get('valor_total') is not None:
                top_after = float(str(extracted.get('valor_total')).replace('.', '').replace(',', '.'))
        except Exception:
            top_after = None

        if computed_after is not None and computed_after > 0:
            # if close agreement, keep top_after; otherwise perform LLM verification
            if top_after is not None and abs(computed_after - top_after) <= 0.5:
                # in close agreement, keep reported top value
                ag['valor_total_calc'] = top_after
            else:
                # attempt LLM verification (LLM-first policy): ask LLM to decide which to keep
                try:
                    from . import llm_helper
                    # pass items and a small context (if available)
                    items = extracted.get('itens') or []
                    context_text = None
                    try:
                        context_text = record.get('ocr_text') or None
                    except Exception:
                        context_text = None
                    llm_resp = llm_helper.verify_total_with_llm(items, top_after, context_text=context_text)
                    if llm_resp.get('ok'):
                        decision = (llm_resp.get('decision') or '').lower() if llm_resp.get('decision') else None
                        llm_total = llm_resp.get('llm_total')
                        conf = llm_resp.get('confidence')
                        if decision == 'keep_top':
                            # keep the original top_after
                            report['notes'].append(f"LLM verification: keep_top (confidence={conf})")
                            ag['valor_total_calc'] = top_after if top_after is not None else computed_after
                        elif decision == 'use_items':
                            # LLM explicitly prefers items sum
                            extracted['valor_total'] = computed_after
                            report['filled']['valor_total'] = computed_after
                            report['notes'].append(f"LLM verification: use_items (confidence={conf}); valor_total set to {computed_after}")
                            ag['valor_total_calc'] = computed_after
                        else:
                            # uncertain: use LLM suggested total if present and confidence high, else fall back to computed
                            if llm_total is not None and conf is not None and conf >= 0.6:
                                extracted['valor_total'] = llm_total
                                report['filled']['valor_total'] = llm_total
                                report['notes'].append(f"LLM suggested total used (confidence={conf}) -> {llm_total}")
                                ag['valor_total_calc'] = llm_total
                            else:
                                # no confident LLM result: fall back to computed sum and annotate
                                extracted['valor_total'] = computed_after
                                report['filled']['valor_total'] = computed_after
                                report['notes'].append(f"LLM uncertain or unavailable; valor_total set to sum(itens)={computed_after}")
                                ag['valor_total_calc'] = computed_after
                    else:
                        # LLM not available or failed: fallback to computed_after but note reason
                        extracted['valor_total'] = computed_after
                        report['filled']['valor_total'] = computed_after
                        reason = llm_resp.get('reason') or llm_resp.get('error') or 'llm_fail'
                        report['notes'].append(f"LLM not available/failed ({reason}); valor_total set to sum(itens)={computed_after}")
                        ag['valor_total_calc'] = computed_after
                except Exception as e:
                    # defensive fallback
                    extracted['valor_total'] = computed_after
                    report['filled']['valor_total'] = computed_after
                    report['notes'].append(f"LLM verification error: {e}; valor_total set to sum(itens)={computed_after}")
                    ag['valor_total_calc'] = computed_after
    except Exception:
        pass

    return extracted, {'report': report, 'aggregates': ag}
