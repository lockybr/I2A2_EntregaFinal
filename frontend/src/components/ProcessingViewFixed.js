import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './ProcessingView.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PIPELINE_ORDER = ['ingestao', 'preprocessamento', 'ocr', 'nlp', 'validacao', 'finalizado'];
const PIPELINE_LABELS = {
  ingestao: 'Ingestão',
  preprocessamento: 'Pré-processamento',
  ocr: 'OCR',
  nlp: 'NLP',
  validacao: 'Validação',
  finalizado: 'Finalizado',
};
const ICONS = {
  ingestao: '📥',
  preprocessamento: '⚙️',
  ocr: '🔎',
  nlp: '🤖',
  validacao: '✅',
  finalizado: '🏁',
};
const PIPELINE_STEPS = PIPELINE_ORDER.map((name, idx) => ({ id: idx + 1, name, icon: ICONS[name] || '•' }));

function ProcessingViewFixed({ docs = [] }) {
  const [docsList, setDocsList] = useState([]); // {id, filename, status}
  const [dashboard, setDashboard] = useState({ total: 0, finalizado: 0, erro: 0, processing: 0, recent: [] });
  const [docId, setDocId] = useState(null);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pollTries, setPollTries] = useState(0);
  const [selectedTab, setSelectedTab] = useState('dados');
  const pollRef = useRef(null);
  const mounted = useRef(true);

  // Load list of documents (either provided via props or from API)
  useEffect(() => {
    const load = async () => {
      if (docs && docs.length) {
        // docs prop may be an array of ids or full objects
        setDocsList(docs.map(d => (typeof d === 'string' ? { id: d, filename: d } : d)));
        setDocId(typeof docs[0] === 'string' ? docs[0] : docs[0].id);
        return;
      }
      try {
        const res = await axios.get(`${API_URL}/api/v1/documents`);
        const list = res.data?.documents || [];
        setDocsList(list);
        if (list.length) setDocId(list[0].id);
        // compute basic dashboard stats (normalize status strings defensively)
        const normalizeStatus = (s) => (s || '').toString().trim().toLowerCase();
        const total = list.length;
        let finalizado = 0, erro = 0, processing = 0;
        for (const d of list) {
          const st = normalizeStatus(d.status);
          if (st === 'finalizado' || st === 'done' || st === 'completed') finalizado += 1;
          else if (st === 'erro' || st === 'error' || st === 'failed') erro += 1;
          else processing += 1;
        }
        // sort recent by uploaded_at if available, fallback to original order
        const recent = (list.slice().sort((a,b) => (b.uploaded_at || '').localeCompare(a.uploaded_at || ''))).slice(0,6);
        setDashboard({ total, finalizado, erro, processing, recent });
      } catch (e) {
        console.warn('Could not load documents list', e.message);
      }
    };
    load();
  }, [docs]);

  // Polling for selected document (interval-based, avoids stale closure on `status`)
  useEffect(() => {
    mounted.current = true;
    if (!docId) return () => { mounted.current = false; };
  // reset poll counter (no-op, pollTries removed)

    const fetchStatus = async ({ suppressLoading = false } = {}) => {
      if (!suppressLoading) setLoading(true);
      try {
        const res = await axios.get(`${API_URL}/api/v1/documents/${docId}/results`);
        const body = res.data;
        // Parse raw_extracted (LLM output) if present
        let parsed = null;
        if (body.raw_extracted) parsed = tryParseMaybeEscapedJson(body.raw_extracted);

        // helper: consider some string values as garbage (boilerplate/instructions)
        const isGarbageString = (v) => {
          if (v === null || v === undefined) return true;
          if (typeof v !== 'string') return false;
          const s = v.trim();
          if (!s) return true;
          if (s.length <= 3) return true;
          // common noisy tokens from OCR/LLM
          if (/\b(RECEBE|VISUALIZE|BOLETO|VISUALIZAR|NFE|NF-e|NF-E|NFE-)\b/i.test(s)) return true;
          return false;
        };

        const normalizeNumbers = (x) => {
          if (x === null || x === undefined) return x;
          if (typeof x === 'number') return x;
          if (typeof x === 'string') {
            const cleaned = x.replace(/[^0-9,\.\-]/g, '').replace(/\./g, '').replace(/,/g, '.');
            const n = parseFloat(cleaned);
            return isNaN(n) ? x : n;
          }
          return x;
        };

        // Merge parsed into extracted_data, preferring parsed when existing data looks like garbage
        if (parsed && typeof parsed === 'object') {
          body.extracted_data = body.extracted_data || {};
          // if parsed has nested objects (emitente/destinatario), deep-merge them
          for (const k of Object.keys(parsed)) {
            const pval = parsed[k];
            const existing = body.extracted_data[k];
            if (pval && typeof pval === 'object' && !Array.isArray(pval)) {
              body.extracted_data[k] = deepMerge(existing || {}, pval);
            } else if (k === 'itens' && Array.isArray(parsed.itens)) {
              const existingItems = Array.isArray(existing) ? existing : [];
              if (!existingItems.length || existingItems.some(it => isGarbageString(it?.descricao))) {
                body.extracted_data.itens = parsed.itens.map(it => ({
                  ...it,
                  valor_unitario: normalizeNumbers(it.valor_unitario),
                  valor_total: normalizeNumbers(it.valor_total),
                }));
              }
            } else {
              // scalar values: accept parsed when existing is missing/garbage
              if (existing === null || existing === undefined || (typeof existing === 'string' && isGarbageString(existing))) {
                if (k === 'valor_total' || k === 'numero_nota') {
                  body.extracted_data[k] = normalizeNumbers(pval);
                } else {
                  body.extracted_data[k] = pval;
                }
              }
            }
          }
        }

        // If extracted_data still missing core fields, attempt simple OCR heuristics
        if (!body.extracted_data || Object.keys(body.extracted_data).length === 0) {
          if (body.ocr_text) {
            const heur = simpleClientParser(body.ocr_text);
            if (heur && Object.keys(heur).length) {
              body.extracted_data = { ...(body.extracted_data || {}), ...heur };
            }
          }
        }

        // If we still have missing nested fields but raw_extracted contains JSON-like values,
        // try a tolerant extraction from the raw LLM output (regex-based) and deep-merge.
        if (body.raw_extracted && body.extracted_data) {
          const hasUseful = (obj) => obj && typeof obj === 'object' && Object.values(obj).some(v => v !== null && v !== undefined && !(typeof v === 'string' && v.trim() === ''));
          // if emitente/destinatario look empty, attempt extraction
          const emitenteEmpty = !hasUseful(body.extracted_data.emitente);
          const destinatarioEmpty = !hasUseful(body.extracted_data.destinatario);
          const topEmpty = body.extracted_data.valor_total === null || body.extracted_data.valor_total === undefined;
          if (emitenteEmpty || destinatarioEmpty || topEmpty) {
            const tolerant = extractFromRawExtracted(body.raw_extracted);
            if (tolerant && Object.keys(tolerant).length) {
              body.extracted_data = deepMerge(body.extracted_data || {}, tolerant);
            }
          }
        }
        // If impostos fields still look empty, try extracting from OCR text
        if (body.ocr_text && body.extracted_data) {
          const imp = body.extracted_data.impostos || {};
          const hasImp = imp && Object.values(imp).some(v => v && (typeof v !== 'object' || Object.values(v).some(x => x !== null && x !== undefined)));
          if (!hasImp) {
            const taxes = extractTaxesFromText(body.ocr_text);
            if (taxes && taxes.impostos) {
              body.extracted_data.impostos = deepMerge(body.extracted_data.impostos || {}, taxes.impostos);
            }
          }
        }
        if (mounted.current) {
          setStatus(body.status);
          setProgress(body.progress ?? 0);
          setResults(body);
          setError(null);
        }
        return body.status;
      } catch (err) {
        if (mounted.current) setError(err.response?.data?.detail || err.message || 'Erro ao buscar resultado');
        return 'erro';
      } finally {
        if (!suppressLoading && mounted.current) setLoading(false);
      }
    };

    // clear any existing interval
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    let tries = 0;
    (async () => {
  const s = await fetchStatus();
  tries += 1;
  setPollTries(tries);
      if (['finalizado', 'erro'].includes(s)) return;
      pollRef.current = setInterval(async () => {
        if (!mounted.current) return;
        // suppress loading on recurrent polls to avoid UI flicker
        const st = await fetchStatus({ suppressLoading: true });
  tries += 1;
  setPollTries(tries);
        if (['finalizado', 'erro'].includes(st) || tries >= 300) {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      }, 2000);
    })();

    return () => {
      mounted.current = false;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  const currentStep = PIPELINE_ORDER.indexOf(status) + 1 || 0;

  const renderPipeline = () => (
    <div className="pipeline">
      {PIPELINE_STEPS.map(step => {
        const stepIndex = PIPELINE_ORDER.indexOf(step.name) + 1;
        const cls = `pipeline-step ${stepIndex < currentStep ? 'active' : ''} ${stepIndex === currentStep ? 'current' : ''}`;
        return (
          <div key={step.id} className={cls} title={step.name}>
            <div className="step-icon">{step.icon}</div>
            <div className="step-name">{PIPELINE_LABELS[step.name] || step.name}</div>
          </div>
        );
      })}
    </div>
  );

  const refreshDocsList = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/v1/documents`);
      const list = res.data?.documents || [];
      setDocsList(list);
      // update dashboard as well
      const normalizeStatus = (s) => (s || '').toString().trim().toLowerCase();
      const total = list.length;
      let finalizado = 0, erro = 0, processing = 0;
      for (const d of list) {
        const st = normalizeStatus(d.status);
        if (st === 'finalizado' || st === 'done' || st === 'completed') finalizado += 1;
        else if (st === 'erro' || st === 'error' || st === 'failed') erro += 1;
        else processing += 1;
      }
      const recent = (list.slice().sort((a,b) => (b.uploaded_at || '').localeCompare(a.uploaded_at || ''))).slice(0,6);
      setDashboard({ total, finalizado, erro, processing, recent });
    } catch (e) {
      console.warn('Could not refresh documents list', e.message);
    }
  };

  // Ensure the documents list is loaded on mount (some environments missed the initial load)
  useEffect(() => {
    if (!docs || docs.length === 0) {
      refreshDocsList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const downloadJSON = () => {
    if (!results) return;
    const payload = {
      id: results.id || docId,
      filename: results.filename,
      extracted: results.extracted_data || null,
      raw_extracted: results.raw_extracted || null,
      ocr_text: results.ocr_text || null,
      _meta: { exported_at: new Date().toISOString() }
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeName = (results.filename || docId || 'document').replace(/[^a-zA-Z0-9._-]/g, '_');
    a.download = `${safeName}-extracted.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const downloadText = (format) => {
    if (!results) return;
    const data = results.extracted_data || {};
    let content = '';
    let mime = 'text/plain';
    const safeName = (results.filename || docId || 'document').replace(/[^a-zA-Z0-9._-]/g, '_');
    if (format === 'xml') {
      mime = 'application/xml';
      // generate a simple XML representation from the extracted JSON
      const header = `<?xml version="1.0" encoding="UTF-8"?>\n<document id="${results.id || docId}" filename="${results.filename || ''}">\n`;
      const footer = '\n</document>';
      const bodyXml = jsonToXml(data, 'extracted');
      content = header + bodyXml + footer;
    } else if (format === 'csv') {
      mime = 'text/csv';
      // build a combined CSV: top-level document fields, then items table (if any)
      const docFields = ['numero_nota', 'chave_acesso', 'data_emissao', 'valor_total', 'emitente.razao_social', 'emitente.cnpj', 'destinatario.razao_social', 'destinatario.cnpj', 'natureza_operacao', 'forma_pagamento'];
      const headerRow = docFields.join(',');
      const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const docValues = docFields.map(f => {
        let v = get(f, '');
        if (v === '—') v = '';
        return escape(v);
      }).join(',');

      let parts = ['"Documento Field","Value"', ...docFields.map((f,i)=> `${escape(f)},${docValues.split(',')[i]}`)];

      // add items section
      if (data && Array.isArray(data.itens) && data.itens.length) {
        parts.push('');
        parts.push('Itens');
        const itemHeader = ['Código','Descrição','NCM','CFOP','CSOSN','Unid','Qtde','Valor Unit','Valor Total'].join(',');
        parts.push(itemHeader);
        const rows = data.itens.map(it => [it.codigo || '', it.descricao || '', it.ncm || '', it.cfop || '', it.csosn || it.cst || '', it.unidade || '', it.quantidade || '', it.valor_unitario || '', it.valor_total || ''].map(c => escape(c)).join(','));
        parts = parts.concat(rows);
      }

      content = parts.join('\n');
    } else {
      mime = 'text/plain';
      content = results.raw_extracted ? stripCodeFences(results.raw_extracted) : (results.ocr_text || JSON.stringify(data, null, 2));
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${safeName}-extracted.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const escapeXml = (unsafe) => {
    return String(unsafe).replace(/[<>&\"]/g, function (c) {
      switch (c) {
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '&': return '&amp;';
        case '"': return '&quot;';
        default: return c;
      }
    });
  };

  // Convert JSON to a simple XML representation
  const jsonToXml = (obj, nodeName = 'root') => {
    if (obj === null || obj === undefined) return `<${nodeName}/>`;
    if (typeof obj !== 'object') {
      return `<${nodeName}>${escapeXml(String(obj))}</${nodeName}>`;
    }
    if (Array.isArray(obj)) {
      // For arrays, repeat the nodeName for each item
      return obj.map(item => jsonToXml(item, nodeName)).join('');
    }
    let inner = '';
    for (const k of Object.keys(obj)) {
      inner += jsonToXml(obj[k], k);
    }
    return `<${nodeName}>${inner}</${nodeName}>`;
  };

  const stripCodeFences = (s) => {
    if (!s || typeof s !== 'string') return s;
    let out = s.trim();
    out = out.replace(/^```(?:json)?\s*/i, '');
    out = out.replace(/\s*```$/i, '');
    return out;
  };

  const tryParseMaybeEscapedJson = (s) => {
    if (typeof s !== 'string') return null;
    let candidate = stripCodeFences(s);
    try {
      return JSON.parse(candidate);
    } catch (e) {
      try {
        const unescaped = candidate.replace(/\\n/g, '\n').replace(/\\t/g, '\t');
        return JSON.parse(unescaped);
      } catch (e2) {
        if (/^".*"$/.test(candidate.trim())) {
          try {
            const once = JSON.parse(candidate);
            return typeof once === 'string' ? JSON.parse(once) : once;
          } catch (e3) {
            return null;
          }
        }
        return null;
      }
    }
  };

  // If raw_extracted is not parseable as JSON, try to pull a few common fields using regex
  const extractFromRawExtracted = (raw) => {
    if (!raw || typeof raw !== 'string') return {};
    const txt = stripCodeFences(raw);
    const out = {};
    try {
      // emitente.razao_social
      const emitR = txt.match(/"emitente"\s*:\s*\{[\s\S]*?"razao_social"\s*:\s*"([^"]+)"/i);
      if (emitR) out.emitente = { ...(out.emitente || {}), razao_social: emitR[1].trim() };
      const emitC = txt.match(/"emitente"[\s\S]*?"cnpj"\s*:\s*"([^"]+)"/i);
      if (emitC) out.emitente = { ...(out.emitente || {}), cnpj: emitC[1].trim() };

      const destR = txt.match(/"destinatario"\s*:\s*\{[\s\S]*?"razao_social"\s*:\s*"([^"]+)"/i);
      if (destR) out.destinatario = { ...(out.destinatario || {}), razao_social: destR[1].trim() };
      const destE = txt.match(/"destinatario"[\s\S]*?"endereco"\s*:\s*"([^"]+)"/i);
      if (destE) out.destinatario = { ...(out.destinatario || {}), endereco: destE[1].trim() };

      const numero = txt.match(/"numero_nota"\s*:\s*"?([0-9\.-]+)"?/i);
      if (numero) out.numero_nota = numero[1].trim();

      const data = txt.match(/"data_emissao"\s*:\s*"([^"]+)"/i) || txt.match(/(\d{2}\/\d{2}\/\d{4})/);
      if (data) out.data_emissao = data[1].trim();

      const valor = txt.match(/"valor_total"\s*:\s*([0-9\.,]+)/i) || txt.match(/Valor Total[\s\S]*?(?:R\$\s*)?([0-9\.,]+)/i) || txt.match(/VALOR TOTAL DA NOTA[\s\S]*?(?:R\$\s*)?([0-9\.,]+)/i);
      if (valor) {
        const cleaned = String(valor[1]).replace(/[^0-9,\.]/g, '').replace(/\./g, '').replace(/,/g, '.');
        const n = parseFloat(cleaned);
        if (!isNaN(n)) out.valor_total = n;
      }
    } catch (e) {
      // swallow
    }
    return out;
  };

  // Try to extract common tax fields from OCR/raw text when impostos are missing
  const extractTaxesFromText = (text) => {
    if (!text || typeof text !== 'string') return {};
    const out = { impostos: { icms: {}, ipi: {}, pis: {}, cofins: {} } };
    const txt = text;
    const toNum = (s) => {
      if (s == null) return null;
      const cleaned = String(s).replace(/[^0-9,\.\-]/g, '').replace(/\./g, '').replace(/,/g, '.');
      const n = parseFloat(cleaned);
      return isNaN(n) ? null : n;
    };

    try {
      // Look for explicit ICMS value lines
      const icmsMatch = txt.match(/ICMS[^\n\r:\-]*[:\-]?[^\n\r]*?([0-9]{1,3}(?:[.,][0-9]{2})?)/i);
      if (icmsMatch) out.impostos.icms.valor = toNum(icmsMatch[1]);
      const icmsAliq = txt.match(/ICMS[^%\n\r]*?([0-9]{1,2}(?:[.,][0-9]{1,2})?)%/i);
      if (icmsAliq) out.impostos.icms.aliquota = toNum(icmsAliq[1]);
      const icmsBase = txt.match(/BASE\s*DE\s*C[AÁ]LCULO[^\n\r]*[:\-]?[^\n\r]*?([0-9\.,]+)/i);
      if (icmsBase) out.impostos.icms.base_calculo = toNum(icmsBase[1]);

      // IPI
      const ipiMatch = txt.match(/IPI[^\n\r:\-]*[:\-]?[^\n\r]*?([0-9]{1,3}(?:[.,][0-9]{2})?)/i);
      if (ipiMatch) out.impostos.ipi.valor = toNum(ipiMatch[1]);

      // PIS
      const pisMatch = txt.match(/PIS[^\n\r:\-]*[:\-]?[^\n\r]*?([0-9]{1,3}(?:[.,][0-9]{2})?)/i);
      if (pisMatch) out.impostos.pis.valor = toNum(pisMatch[1]);

      // COFINS
      const cofMatch = txt.match(/COFINS[^\n\r:\-]*[:\-]?[^\n\r]*?([0-9]{1,3}(?:[.,][0-9]{2})?)/i);
      if (cofMatch) out.impostos.cofins.valor = toNum(cofMatch[1]);

      // Vlr Aprox dos Tributos (total taxes) -- split Federal/Estadual if present
      const approx = txt.match(/Vlr\s*Aprox\s+dos\s+Tributos\s*[:\-]?\s*(?:R\$\s*)?([0-9\.,]+)/i);
      if (approx) {
        const n = toNum(approx[1]);
        // if we have federal/estadual pair
        const pair = txt.match(/Vlr\s*Aprox[\s\S]*?([0-9\.,]+)\s*Federal\s*\/?\s*R?\$?\s*([0-9\.,]+)\s*Estad/i);
        if (pair) {
          const fed = toNum(pair[1]);
          const est = toNum(pair[2]);
          // heuristically assign
          if (est != null) {
            out.impostos.icms.valor = out.impostos.icms.valor || est;
          }
          if (fed != null) {
            // assign to pis+cofins combined if individual missing
            if (!out.impostos.pis.valor && !out.impostos.cofins.valor) {
              // split equally as a fallback
              out.impostos.pis.valor = out.impostos.pis.valor || Math.round((fed / 2) * 100) / 100;
              out.impostos.cofins.valor = out.impostos.cofins.valor || Math.round((fed / 2) * 100) / 100;
            }
          }
        } else {
          // assign total to icms if none
          if (!out.impostos.icms.valor) out.impostos.icms.valor = n;
        }
      }
    } catch (e) {
      // ignore parse errors
    }

    return out;
  };

  // Deep merge: set values from src into dst when dst is missing/null.
  const deepMerge = (dst, src) => {
    if (!src) return dst;
    if (!dst || typeof dst !== 'object') return src;
    const out = Array.isArray(dst) ? [...dst] : { ...dst };
    for (const k of Object.keys(src)) {
      const sv = src[k];
      const dv = out[k];
      if (sv && typeof sv === 'object' && !Array.isArray(sv)) {
        out[k] = deepMerge(dv && typeof dv === 'object' ? dv : {}, sv);
      } else if (Array.isArray(sv)) {
        // prefer src array when dst is empty or contains garbage
        if (!Array.isArray(dv) || dv.length === 0) out[k] = sv;
        else out[k] = dv;
      } else {
        if (dv === null || dv === undefined || (typeof dv === 'string' && String(dv).trim().length <= 3)) {
          out[k] = sv;
        } else {
          out[k] = dv;
        }
      }
    }
    return out;
  };

  // Client-side heuristic parser to salvage some fields from OCR text when extracted_data is empty.
    const simpleClientParser = (ocrText) => {
    if (!ocrText || typeof ocrText !== 'string') return {};
    const out = {};
    // CNPJ: 14 digits (allow punctuation)
    const cnpjMatch = ocrText.match(/(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}|\d{14})/);
    if (cnpjMatch) out.emitente = { ...(results?.extracted_data?.emitente || {}), cnpj: cnpjMatch[0] };
    // Chave de acesso: 44 digits
    const chaveMatch = ocrText.match(/(\d{44})/);
    if (chaveMatch) { out.chave_acesso = chaveMatch[0]; }
    // Date (DD/MM/YYYY)
    const dateMatch = ocrText.match(/(\d{2}\/\d{2}\/\d{4})/);
    if (dateMatch) out.data_emissao = dateMatch[0];
    // Total/Valor: look for R$ or numbers like 1234.56 or 1.234,56
    const moneyMatch = ocrText.match(/R\$\s*[0-9.,]+|\d{1,3}(?:[.,]\d{3})*[.,]\d{2}/g);
    if (moneyMatch && moneyMatch.length) {
      // pick the largest numeric value
      const nums = moneyMatch.map(s => s.replace(/[^0-9,.,-]/g, '').replace(/\./g, '').replace(/,/g, '.')).map(parseFloat).filter(n => !isNaN(n));
      if (nums.length) {
        const max = Math.max(...nums);
        out.valor_total = max;
      }
    }
    return out;
  };

  // small helper: pretty print JSON but limit size to avoid UI jank
  const safeJsonStringify = (obj, maxLen = 20000) => {
    try {
      const raw = JSON.stringify(obj, null, 2);
      if (raw.length > maxLen) return raw.slice(0, maxLen) + '\n... (truncated)';
      return raw;
    } catch (e) {
      return String(obj);
    }
  };

  // Render helpers for tabs
  // Get value by path (supports nested keys and fallback recursive search)
  const findKeyInObject = (obj, key) => {
    if (!obj || typeof obj !== 'object') return undefined;
    if (key in obj) return obj[key];
    for (const k of Object.keys(obj)) {
      try {
        const v = obj[k];
        if (typeof v === 'object') {
          const found = findKeyInObject(v, key);
          if (found !== undefined) return found;
        }
      } catch (e) { /* ignore */ }
    }
    return undefined;
  };

  const get = (path, fallback = '—') => {
    // support aliases: allow requesting logical path and try common alternative keys
    const KEY_ALIASES = {
      'numero_nota': ['numero_nota', 'numero', 'nfe_numero', 'numeroNota', 'numero_da_nota', 'nf_numero', 'nota_numero'],
      'chave_acesso': ['chave_acesso', 'chave', 'chave_de_acesso', 'access_key', 'chaveAcesso'],
      'data_emissao': ['data_emissao', 'data', 'data_emissao_nf', 'dataEmissao', 'data_emissao_nf', 'data_emissao_nfe'],
      'data_saida': ['data_saida', 'data_saida_nf', 'data_saida_nfe'],
      'serie': ['serie', 'série', 'serie_nf'],
      'valor_total': ['valor_total', 'total', 'valor', 'valor_da_nota', 'total_value', 'valorTotal'],
      'valor_produtos': ['valor_produtos', 'valor_produto', 'valor_produtos_total', 'total_produtos'],
      'valor_frete': ['valor_frete', 'frete', 'valor_frete_total'],
      'valor_desconto': ['valor_desconto', 'desconto', 'valor_descontos'],
      'emitente.razao_social': ['emitente.razao_social', 'emitente.nome', 'emitente.razao', 'emitente.name', 'emitente.nome_fantasia'],
      'emitente.nome_fantasia': ['emitente.nome_fantasia', 'emitente.fantasia', 'emitente.nomeFantasia'],
      'emitente.cnpj': ['emitente.cnpj', 'emitente.cpf', 'cnpj', 'cnpj_emitente', 'emitente_cnpj'],
      'destinatario.razao_social': ['destinatario.razao_social', 'destinatario.nome', 'destinatario.name', 'destinatario.nome_fantasia'],
      'destinatario.nome_fantasia': ['destinatario.nome_fantasia', 'destinatario.fantasia'],
      'codigos_fiscais.cfop': ['codigos_fiscais.cfop', 'cfop'],
      'codigos_fiscais.cst': ['codigos_fiscais.cst', 'cst'],
      'codigos_fiscais.ncm': ['codigos_fiscais.ncm', 'ncm'],
      'codigos_fiscais.csosn': ['codigos_fiscais.csosn', 'csosn'],
      'natureza_operacao': ['natureza_operacao', 'natureza', 'naturezaOperacao'],
      'forma_pagamento': ['forma_pagamento', 'formaPagamento', 'condicao_pagamento', 'cond_pag'],
    };
    try {
      // if aliases known for this logical path, try them in order
      const aliases = KEY_ALIASES[path] || [path];
      for (const a of aliases) {
        const parts = a.split('.');
        let cur = results?.extracted_data;
        let ok = true;
        for (const p of parts) {
          if (!cur || typeof cur !== 'object' || !(p in cur)) { ok = false; break; }
          cur = cur[p];
        }
        if (ok && cur !== undefined && cur !== null) return cur;
      }
      // fallback: search recursively for last part of original path
      const last = path.split('.').slice(-1)[0];
      const found = findKeyInObject(results?.extracted_data, last);
      if (found !== undefined && found !== null) return found;
      // also try top-level
      if (results?.extracted_data && (results.extracted_data[path] || results.extracted_data[last])) return results.extracted_data[path] || results.extracted_data[last];
      return fallback;
    } catch (e) {
      return fallback;
    }
  };

  const renderDadosNota = () => (
    <div className="section-grid">
      <div className="card"><label>Número da Nota</label><div className="value">{get('numero_nota')}</div></div>
      <div className="card"><label>Série</label><div className="value">{get('serie')}</div></div>
      <div className="card"><label>Chave de Acesso</label><div className="value monospace">{get('chave_acesso')}</div></div>
      <div className="card"><label>Data de Emissão</label><div className="value">{get('data_emissao')}</div></div>
      <div className="card"><label>Data de Saída</label><div className="value">{get('data_saida')}</div></div>
      <div className="card"><label>Natureza da Operação</label><div className="value">{get('natureza_operacao')}</div></div>
    </div>
  );

  const renderEmitente = () => {
    const e = results?.extracted_data?.emitente || {};
    return (
      <div className="section-grid">
        <div className="card"><label>Razão Social</label><div className="value">{e.razao_social ?? '—'}</div></div>
        <div className="card"><label>Nome Fantasia</label><div className="value">{e.nome_fantasia ?? '—'}</div></div>
        <div className="card"><label>CNPJ</label><div className="value">{e.cnpj ?? '—'}</div></div>
        <div className="card"><label>Inscrição Estadual</label><div className="value">{e.inscricao_estadual ?? '—'}</div></div>
        <div className="card"><label>Endereço</label><div className="value">{e.endereco ?? '—'}</div></div>
        <div className="card"><label>Bairro</label><div className="value">{e.bairro ?? '—'}</div></div>
        <div className="card"><label>Município</label><div className="value">{e.municipio ?? '—'}</div></div>
        <div className="card"><label>UF</label><div className="value">{e.uf ?? '—'}</div></div>
        <div className="card"><label>CEP</label><div className="value">{e.cep ?? '—'}</div></div>
      </div>
    );
  };

  const renderDestinatario = () => {
    const d = results?.extracted_data?.destinatario || {};
    return (
      <div className="section-grid">
        <div className="card"><label>Razão Social</label><div className="value">{d.razao_social ?? '—'}</div></div>
        <div className="card"><label>CNPJ</label><div className="value">{d.cnpj ?? '—'}</div></div>
        <div className="card"><label>Inscrição Estadual</label><div className="value">{d.inscricao_estadual ?? '—'}</div></div>
        <div className="card"><label>Endereço</label><div className="value">{d.endereco ?? '—'}</div></div>
        <div className="card"><label>Bairro</label><div className="value">{d.bairro ?? '—'}</div></div>
        <div className="card"><label>Município</label><div className="value">{d.municipio ?? '—'}</div></div>
        <div className="card"><label>UF</label><div className="value">{d.uf ?? '—'}</div></div>
        <div className="card"><label>CEP</label><div className="value">{d.cep ?? '—'}</div></div>
      </div>
    );
  };

  const renderItens = () => {
    const items = results?.extracted_data?.itens || [];
    return (
      <div className="items-table">
        <table>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>NCM</th>
              <th>CFOP</th>
              <th>CSOSN</th>
              <th>Unid.</th>
              <th>Qtd.</th>
              <th>Valor Unit.</th>
              <th>Valor Total</th>
            </tr>
          </thead>
          <tbody>
            {items.length ? items.map((it, idx) => (
              <tr key={idx}>
                <td>{it.codigo ?? '—'}</td>
                <td>{it.descricao ?? '—'}</td>
                <td>{it.ncm ?? '—'}</td>
                <td>{it.cfop ?? '—'}</td>
                <td>{it.csosn ?? it.cst ?? '—'}</td>
                <td>{it.unidade ?? '—'}</td>
                <td>{it.quantidade ?? '—'}</td>
                <td>{it.valor_unitario ?? '—'}</td>
                <td>{it.valor_total ?? '—'}</td>
              </tr>
            )) : (
              <tr><td colSpan={9}>Nenhum item identificado.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    );
  };

  const renderTributos = () => {
    const imp = results?.extracted_data?.impostos || {};
    const renderTax = (name, data) => (
      <div className="tax-card">
        <h4>{name}</h4>
        <div className="card"><label>Alíquota</label><div className="value">{data?.aliquota ?? '—'}</div></div>
        <div className="card"><label>Base de Cálculo</label><div className="value">{data?.base_calculo ?? '—'}</div></div>
        <div className="card"><label>Valor</label><div className="value">{data?.valor ?? '—'}</div></div>
      </div>
    );
    return (
      <div className="taxes-grid">
        {renderTax('ICMS', imp.icms || {})}
        {renderTax('PIS', imp.pis || {})}
        {renderTax('COFINS', imp.cofins || {})}
        {renderTax('IPI', imp.ipi || {})}
      </div>
    );
  };

  const renderTotais = () => (
    <div className="section-grid">
      <div className="card"><label>Valor Total</label><div className="value">{get('valor_total')}</div></div>
      <div className="card"><label>Valor Produtos</label><div className="value">{get('valor_produtos')}</div></div>
      <div className="card"><label>Frete</label><div className="value">{get('valor_frete')}</div></div>
      <div className="card"><label>Descontos</label><div className="value">{get('valor_desconto')}</div></div>
    </div>
  );

  const renderOutros = () => {
    const raw = results?.raw_extracted ?? null;
    const rawFile = results?.raw_file ?? null;
    const tmpPath = results?.tmp_path ?? null;

    // detect binary-like content to avoid dumping huge binary blobs
    const isLikelyBinary = (s) => {
      if (!s || typeof s !== 'string') return false;
      // heuristics: very long strings or many control chars => likely binary
      if (s.length > 20000) return true;
      let nonPrintable = 0;
      for (let i = 0; i < s.length; i++) {
        const code = s.charCodeAt(i);
        // allow tab(9), lf(10), cr(13), space and printable range
        if (code === 9 || code === 10 || code === 13) continue;
        if (code < 32 || code > 126) nonPrintable += 1;
      }
      return nonPrintable > 200;
    };

    return (
    <div className="outros">
      <h4>Raw LLM Output</h4>
      <pre className="raw-text">{raw ? stripCodeFences(raw).slice(0, 20000) : '—'}</pre>
      <h4>Full Extracted JSON</h4>
      <pre className="extracted-json">{safeJsonStringify(results?.extracted_data ?? {})}</pre>
      <h4>OCR Text</h4>
      <pre className="ocr-text">{stripCodeFences(results?.ocr_text ?? '').slice(0, 20000)}</pre>
        <h4>Arquivo Original (raw)</h4>
        {rawFile && !isLikelyBinary(rawFile) ? (
          <pre className="raw-file">{rawFile}</pre>
        ) : (
          <div className="raw-file-binary">
            <p>{rawFile ? 'Arquivo textual muito grande ou contém binário. Faça o download do original para visualização.' : (tmpPath ? 'Arquivo original disponível para download.' : '—')}</p>
            {tmpPath && (
              <a href={`${API_URL}/api/v1/documents/${docId}/download`} className="download-btn">⬇️ Baixar Original</a>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderTabContent = () => {
    switch (selectedTab) {
      case 'dados': return renderDadosNota();
      case 'emitente': return renderEmitente();
      case 'destinatario': return renderDestinatario();
      case 'itens': return renderItens();
      case 'tributos': return renderTributos();
      case 'totais': return renderTotais();
      case 'outros': return renderOutros();
      default: return null;
    }
  };

  return (
    <div className="processing-view results-page">
      <div className="results-header">
        <h1>Resultados da Extração</h1>
        <p>Dados extraídos e organizados por categoria</p>
        {results?.filename && <div className="original-file">Arquivo original: <strong>{results.filename}</strong></div>}
      </div>

      {renderPipeline()}

      <div className="document-selector">
        <label>Selecionar Documento:</label>
        <div className="selector-row">
          <select value={docId || ''} onChange={e => setDocId(e.target.value)} onFocus={() => refreshDocsList()} onClick={() => refreshDocsList()}>
            <option value="">-- selecione --</option>
            {docsList.map(d => {
              const ts = (d.uploaded_at || d.created_at || d.processed_at || '') ? (d.uploaded_at || d.created_at || d.processed_at || '').replace('T', ' ').split('.')[0] : '';
              const label = `${d.filename || d.id}${ts ? ' — ' + ts : ''} — ${d.id}`;
              return (<option key={d.id} value={d.id}>{label}</option>);
            })}
          </select>
          <button onClick={refreshDocsList}>↻ Atualizar</button>
        </div>
      </div>

      {/* Dashboard removed from this view — use the dedicated Dashboard screen for analytics */}

      <div className="meta-row">
        <div>Status: <strong>{status ?? '---'}</strong></div>
        <div>Progresso: <strong>{progress}%</strong></div>
      </div>

      <div className="tabs">
        <button className={selectedTab === 'dados' ? 'active' : ''} onClick={() => setSelectedTab('dados')}>Dados da Nota</button>
        <button className={selectedTab === 'emitente' ? 'active' : ''} onClick={() => setSelectedTab('emitente')}>Emitente</button>
        <button className={selectedTab === 'destinatario' ? 'active' : ''} onClick={() => setSelectedTab('destinatario')}>Destinatário</button>
        <button className={selectedTab === 'itens' ? 'active' : ''} onClick={() => setSelectedTab('itens')}>Itens</button>
        <button className={selectedTab === 'tributos' ? 'active' : ''} onClick={() => setSelectedTab('tributos')}>Tributos</button>
        <button className={selectedTab === 'totais' ? 'active' : ''} onClick={() => setSelectedTab('totais')}>Totais</button>
        <button className={selectedTab === 'outros' ? 'active' : ''} onClick={() => setSelectedTab('outros')}>Outros</button>
      </div>

      <div className="tab-content">
        {error && <div className="error">Erro: {error}</div>}
        {loading && <div className="loading">Carregando...</div>}
        {!results && !loading && <div>Nenhum resultado disponível para o documento selecionado.</div>}
        {results && renderTabContent()}
      </div>

      <div className="results-controls bottom-controls">
        <button onClick={downloadJSON} className="export-btn">📥 Exportar JSON</button>
        <button onClick={() => downloadText('xml')} className="export-btn">📥 Exportar XML</button>
        <button onClick={() => downloadText('csv')} className="export-btn">📥 Exportar CSV</button>
      </div>
    </div>
  );
}

export default ProcessingViewFixed;
