"""Lightweight helper to ask OpenRouter (or configured OpenRouter-compatible endpoint)
to verify numeric totals when there's a mismatch between LLM-parsed top-level and computed sums.

This module uses simple HTTP requests so it doesn't depend on langchain. It is best-effort:
- If OPENROUTER_API_KEY is not set, it returns {'ok': False, 'reason': 'no_key'}.
- It expects the OpenRouter-compatible chat completions endpoint.
"""
import os
import json
import requests
from typing import Dict, Any, Optional

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_KEY')
OPENROUTER_DEFAULT_MODEL = os.environ.get('OPENROUTER_MODEL') or 'minimax/minimax-m2:free'


def _build_prompt(items: list, reported_total: Optional[float], context_text: Optional[str] = None) -> str:
    items_summary = []
    for it in items:
        desc = it.get('descricao') or it.get('desc') or ''
        qty = it.get('quantidade') or it.get('qtd') or ''
        v = it.get('valor_total') if it.get('valor_total') is not None else it.get('valor_unitario')
        items_summary.append(f"- {desc} | qty: {qty} | valor_total: {v}")

    prompt = (
        "Você é um assistente fiscal. Verifique se o valor total informado na nota corresponde à soma dos itens listados.\n"
        "Retorne uma resposta JSON com as chaves: decision (keep_top/use_items/uncertain), llm_total (número ou null), confidence (0.0-1.0), explanation (string).\n"
        "Dados:\n"
    )
    if context_text:
        prompt += f"Contexto (trecho do OCR/extração):\n{context_text}\n\n"
    prompt += "Itens:\n" + "\n".join(items_summary) + "\n\n"
    prompt += f"Valor total declarado: {reported_total}\n\n"
    prompt += (
        "Instruções: faça a soma dos valores de 'valor_total' dos itens quando disponíveis. Se a soma e o valor declarado coincidirem (diferença <= 0.5), use decision='keep_top' e retorne confidence alto. "
        "Se a soma for claramente mais confiável (itens completos e soma > 0 e diferença > 0.5), retorne decision='use_items' e llm_total com a soma. Se não puder decidir, retorne 'uncertain'. Responda apenas em JSON sem texto adicional."
    )
    return prompt


def verify_total_with_llm(items: list, reported_total: Optional[float], context_text: Optional[str] = None, model: Optional[str] = None, timeout: int = 8) -> Dict[str, Any]:
    """Ask the LLM to verify totals. Returns a dict with keys: ok, decision, llm_total, confidence, explanation.
    If no API key or the call fails, returns ok=False and reason.
    """
    if not OPENROUTER_API_KEY:
        return {'ok': False, 'reason': 'no_key'}

    model_to_use = model or OPENROUTER_DEFAULT_MODEL
    prompt = _build_prompt(items, reported_total, context_text)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": "Você é um assistente rigoroso e conciso para verificação de valores fiscais."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300,
        "temperature": 0.0
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code != 200:
            return {'ok': False, 'reason': f'http_{r.status_code}', 'text': r.text[:1000]}
        data = r.json()
        # try to extract assistant content
        content = None
        if isinstance(data, dict):
            # standard OpenRouter shape: choices[0].message.content
            try:
                content = data.get('choices', [])[0].get('message', {}).get('content')
            except Exception:
                content = None
        if not content and isinstance(data, dict) and data.get('result'):
            content = data.get('result')

        if not content:
            return {'ok': False, 'reason': 'no_content', 'raw': data}

        # sanitize: try to extract JSON object from content
        txt = content.strip()
        # common case: content is a JSON object literal
        try:
            parsed = json.loads(txt)
        except Exception:
            # try to find first { ... }
            f = txt.find('{')
            l = txt.rfind('}')
            if f != -1 and l != -1 and l > f:
                try:
                    parsed = json.loads(txt[f:l+1])
                except Exception:
                    parsed = None
            else:
                parsed = None

        if not parsed or not isinstance(parsed, dict):
            return {'ok': False, 'reason': 'parse_failed', 'raw_text': txt[:2000]}

        # normalize fields
        decision = parsed.get('decision') or parsed.get('action') or None
        llm_total = parsed.get('llm_total') if 'llm_total' in parsed else parsed.get('total') if 'total' in parsed else None
        confidence = parsed.get('confidence') if 'confidence' in parsed else None
        explanation = parsed.get('explanation') or parsed.get('reason') or ''
        try:
            if llm_total is not None:
                llm_total = float(llm_total)
        except Exception:
            llm_total = None
        try:
            if confidence is not None:
                confidence = float(confidence)
        except Exception:
            confidence = None

        return {'ok': True, 'decision': decision, 'llm_total': llm_total, 'confidence': confidence, 'explanation': explanation, 'raw': parsed}
    except Exception as e:
        return {'ok': False, 'reason': 'exception', 'error': str(e)}


def extract_field_with_llm(field_name: str, context_text: str, field_description: str = None, model: Optional[str] = None, timeout: int = 8) -> Dict[str, Any]:
    """Ask the LLM to extract a specific field from text. Returns a dict with keys: ok, value, confidence, explanation.
    If no API key or the call fails, returns ok=False and reason.
    """
    if not OPENROUTER_API_KEY:
        return {'ok': False, 'reason': 'no_key'}

    model_to_use = model or OPENROUTER_DEFAULT_MODEL
    
    if not field_description:
        field_descriptions = {
            'natureza_operacao': 'a natureza da operação (ex: VENDA, COMPRA, TRANSFERENCIA, DEVOLUCAO, REMESSA, etc.)',
            'forma_pagamento': 'a forma de pagamento (ex: DINHEIRO, CARTAO, BOLETO, PIX, CHEQUE, CREDITO, DEBITO, A VISTA, A PRAZO, etc.)',
            'cst': 'o código CST (Código de Situação Tributária) - 2 ou 3 dígitos (ex: 00, 10, 20, 101, 102, etc.)',
            'csosn': 'o código CSOSN (Código de Situação da Operação no Simples Nacional) - 3 dígitos (ex: 101, 102, 103, 201, etc.)',
            'aliquota_icms': 'a alíquota do ICMS em percentual (ex: 18%, 12%, 7%, etc.)',
            'cfop': 'o código CFOP (Código Fiscal de Operações e Prestações) - 4 dígitos (ex: 5102, 6102, 1102, etc.)',
            'ncm': 'o código NCM (Nomenclatura Comum do Mercosul) - 8 dígitos (ex: 12345678)'
        }
        field_description = field_descriptions.get(field_name, f'o campo {field_name}')

    prompt = f"""Você é um especialista em documentos fiscais brasileiros. Extraia {field_description} do texto fornecido.

Texto do documento:
        try:
            parsed = json.loads(txt)
        except Exception:
            # try to find first { ... }
            f = txt.find('{')
            l = txt.rfind('}')
            if f != -1 and l != -1 and l > f:
                try:
                    parsed = json.loads(txt[f:l+1])
                except Exception:
                    parsed = None
            else:
                parsed = None

        if not parsed or not isinstance(parsed, dict):
            return {'ok': False, 'reason': 'parse_failed', 'raw_text': txt[:2000]}

        # normalize fields
        decision = parsed.get('decision') or parsed.get('action') or None
        llm_total = parsed.get('llm_total') if 'llm_total' in parsed else parsed.get('total') if 'total' in parsed else None
        confidence = parsed.get('confidence') if 'confidence' in parsed else None
        explanation = parsed.get('explanation') or parsed.get('reason') or ''
        value = parsed.get('value')
        # Post-process for valor_total: reject implausible values (e.g., CNPJ-like numbers)
        try:
            if value is not None:
                value = float(value)
                if field_name == 'valor_total' and value > 10_000_000:
                    value = None
            elif llm_total is not None:
                llm_total = float(llm_total)
                if field_name == 'valor_total' and llm_total > 10_000_000:
                    llm_total = None
        except Exception:
            value = parsed.get('value')
        return {
            'ok': True,
            'value': value if value is not None else llm_total,
            'confidence': confidence,
            'explanation': explanation,
            'raw': parsed
        }
        # extract JSON from content
        txt = content.strip()
        try:
            parsed = json.loads(txt)
        except Exception:
            # try to find first { ... }
            f = txt.find('{')
            l = txt.rfind('}')
            if f != -1 and l != -1 and l > f:
                try:
                    parsed = json.loads(txt[f:l+1])
                except Exception:
                    parsed = None
            else:
                parsed = None

        if not parsed or not isinstance(parsed, dict):
            return {'ok': False, 'reason': 'parse_failed', 'raw_text': txt[:2000]}

        value = parsed.get('value')
        confidence = parsed.get('confidence', 0.0)
        explanation = parsed.get('explanation', '')
        
        try:
            if confidence is not None:
                confidence = float(confidence)
        except Exception:
            confidence = 0.0

        return {'ok': True, 'value': value, 'confidence': confidence, 'explanation': explanation, 'raw': parsed}
    except Exception as e:
        return {'ok': False, 'reason': 'exception', 'error': str(e)}


def extract_items_with_llm(context_text: str, model: Optional[str] = None, timeout: int = 12) -> Dict[str, Any]:
    """Ask the LLM to extract items from text. Returns a dict with keys: ok, items, confidence, explanation.
    If no API key or the call fails, returns ok=False and reason.
    """
    if not OPENROUTER_API_KEY:
        return {'ok': False, 'reason': 'no_key'}

    model_to_use = model or OPENROUTER_DEFAULT_MODEL
    
    prompt = f"""Você é um especialista em documentos fiscais brasileiros. Extraia TODOS os itens/produtos do documento fornecido.

Texto do documento:
{context_text}

Instruções CRÍTICAS:
- Identifique TODOS os produtos/serviços listados - não pare no primeiro item!
- Procure por padrões como código + descrição + valor, ou listas de produtos
- Para cada item encontrado, extraia: descricao, quantidade, unidade, valor_unitario, valor_total, ncm, cfop, cst
- Em notas da Leroy Merlin, procure por códigos de 6-8 dígitos seguidos de descrição
- Em cupons iFood/delivery, procure por linha por linha cada produto
- Retorne um JSON com as chaves: items (array de objetos), confidence (0.0-1.0), explanation (breve explicação)
- Se não encontrar itens, retorne items: []
- Para valores monetários, use formato decimal (ex: 42.50)
- Para códigos (NCM, CFOP, CST), retorne apenas os dígitos
- IMPORTANTE: Continue lendo até o final para capturar todos os itens

Exemplo de formato de retorno:
{{"items": [{{"descricao": "PRODUTO A", "quantidade": 10.0, "unidade": "UN", "valor_unitario": 42.0, "valor_total": 420.0, "ncm": "12345678", "cfop": "5102", "cst": "00"}}], "confidence": 0.9, "explanation": "Encontrados X itens na seção de produtos"}}

Responda apenas em JSON:"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": "Você é um especialista rigoroso em documentos fiscais brasileiros."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.0
    }
    
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code != 200:
            return {'ok': False, 'reason': f'http_{r.status_code}', 'text': r.text[:1000]}
        
        data = r.json()
        content = None
        if isinstance(data, dict):
            try:
                content = data.get('choices', [])[0].get('message', {}).get('content')
            except Exception:
                content = None
        
        if not content:
            return {'ok': False, 'reason': 'no_content', 'raw': data}

        # extract JSON from content
        txt = content.strip()
        try:
            parsed = json.loads(txt)
        except Exception:
            # try to find first { ... }
            f = txt.find('{')
            l = txt.rfind('}')
            if f != -1 and l != -1 and l > f:
                try:
                    parsed = json.loads(txt[f:l+1])
                except Exception:
                    parsed = None
            else:
                parsed = None

        if not parsed or not isinstance(parsed, dict):
            return {'ok': False, 'reason': 'parse_failed', 'raw_text': txt[:2000]}

        items = parsed.get('items', [])
        confidence = parsed.get('confidence', 0.0)
        explanation = parsed.get('explanation', '')
        
        try:
            if confidence is not None:
                confidence = float(confidence)
        except Exception:
            confidence = 0.0

        return {'ok': True, 'items': items, 'confidence': confidence, 'explanation': explanation, 'raw': parsed}
    except Exception as e:
        return {'ok': False, 'reason': 'exception', 'error': str(e)}
