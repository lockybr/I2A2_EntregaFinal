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
