import React, {useEffect, useState, useRef, useCallback} from 'react';
import axios from 'axios';
import './Dashboard.css';
import DocumentModal from './DocumentModal';
import { EyeIcon, DownloadIcon } from './icons/Icons';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function formatCurrency(v){
  if (v === null || v === undefined || v === '') return '—';
  const num = Number(String(v).replace(/[^0-9\-.,]/g,''));
  if (Number.isNaN(num)) return String(v);
  return num.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function StatusBadge({status}){
  const s = (status||'').toLowerCase();
  const cls = s.includes('final') || s.includes('done') || s.includes('ok') ? 'badge-success'
    : s.includes('process') || s.includes('proc') || s.includes('running') ? 'badge-pending'
    : 'badge-error';
  return <span className={`badge ${cls}`}>{status || '—'}</span>;
}

export default function ProcessingHistory({onOpenDocument, uploadedDocs}){
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const initialLoaded = useRef(false);
  const pendingScrollId = useRef(null);
  const [modalOpen, setModalOpen] = useState(false);

  const docsKey = (list)=>{
    try{
      return (list||[]).map(d=>{
        const v = d?.aggregates?.valor_total_calc ?? (d?.extracted_data?.valor_total ?? '');
        const s = `${d.id||''}|${d.status||''}|${d.progress||''}|${String(v)}|${(d?.extracted_data?.emitente?.razao_social||'')}`;
        return s;
      }).join('\n');
    }catch(e){ return JSON.stringify(list||[]); }
  };

  const fetch = useCallback(async (opts = {showLoading: false})=>{
    // Only show the full-screen loading indicator on the very first load to avoid flicker
    if (opts.showLoading) setLoading(true);
    try{
      const res = await axios.get(`${API_URL}/api/v1/documents`);
      const newDocs = res.data?.documents || [];
      // avoid state churn: only update if something meaningful changed
      setDocs(prev => {
        try{
          const prevKey = docsKey(prev);
          const newKey = docsKey(newDocs);
          if (prevKey === newKey) return prev;
        }catch(e){ /* fall through to set */ }
        return newDocs;
      });
      // if there's a pending scroll requested (via uploadedDocs/openProcessing), try to scroll now
      if (pendingScrollId.current) {
        const id = pendingScrollId.current;
        pendingScrollId.current = null;
        setTimeout(()=>{
          const el = document.getElementById(`doc-row-${id}`);
          if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          // keep the selection visible
          setSelectedId(id);
        }, 80);
      }
    }catch(e){
      console.error('Erro ao carregar histórico', e.message||e);
      // don't clobber the existing list on transient errors
    }finally{
      if (opts.showLoading) setLoading(false);
      initialLoaded.current = true;
    }
  }, []);

  // initial load (show loading only on first render)
  useEffect(()=>{ fetch({showLoading: true}); }, [fetch]);

  // polling for updates when component mounted (no loading indicator)
  useEffect(()=>{
    const iv = setInterval(()=>{ fetch({showLoading: false}); }, 2000);
    return () => clearInterval(iv);
  }, [fetch]);

  // handle uploadedDocs coming from App (when user clicks Visualizar)
  useEffect(()=>{
    if (Array.isArray(uploadedDocs) && uploadedDocs.length) {
      const id = uploadedDocs[0]?.id || null;
      if (id) {
        // mark pending scroll; fetch loop will perform the scroll after refreshing docs
        pendingScrollId.current = id;
        // set selection immediately so the UI reflects intent even if list is the same
        setSelectedId(id);
        // ensure we trigger at least one immediate fetch to get fresh metadata
        // but avoid showing the large loading spinner
        fetch({showLoading: false});
      }
    }
  }, [uploadedDocs, fetch]);

  if (loading) return <div className="loading">Carregando processamentos...</div>;

  return (
    <div className="dashboard">
      <div className="dash-header">
        <h2>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginRight:8, verticalAlign:'text-bottom'}}>
            <path d="M3 6h13v13H3z" stroke="#1e3a8a" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M7 6V4a2 2 0 0 1 2-2h6" stroke="#1e3a8a" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Processamentos
        </h2>
        <div className="dash-actions">
          <button className="btn" onClick={fetch} title="Atualizar processamentos">↻ Atualizar</button>
        </div>
      </div>

      <div className="chart-card history-card" style={{padding:'0.5rem'}}>
        <div className="history-table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Status</th>
                <th>Valor Total</th>
                <th>Emitente</th>
                <th>Data da Nota</th>
                <th>Data Processamento</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {docs.map(d=>{
                // Prefer aggregates.valor_total_calc over extracted_data.valor_total for better accuracy
                const val = d?.aggregates?.valor_total_calc ?? d?.extracted_data?.valor_total ?? '';
                const emit = d?.extracted_data?.emitente?.razao_social || d?.extracted_data?.emitente?.nome || '';
                const ts = (d.uploaded_at || d.created_at || '').replace('T',' ').split('.')[0] || '';
                const filename = d.filename || d.id;
                const label = `${filename}${ts? ' — ' + ts : ''} — ${d.id}`;
                // Extract nota emission date
                const dataEmissao = d?.extracted_data?.data_emissao || '';
          return (
            <tr id={`doc-row-${d.id}`} key={d.id} className="history-row" style={d.id === selectedId ? { background: '#f0f9ff' } : undefined}>
                    <td className="col-file" title={label}>
                      <div className="file-cell">
                        <div className="file-name">{filename}</div>
                        <div className="file-sub">{ts} • {d.id.slice(0,8)}</div>
                      </div>
                    </td>
                    <td className="col-status"><StatusBadge status={d.status} /></td>
                    <td className="col-value">R$ {formatCurrency(val)}</td>
                    <td className="col-emitente">{emit || '—'}</td>
                    <td className="col-date-nota">{dataEmissao || '—'}</td>
                    <td className="col-date">{(d.uploaded_at || d.created_at || '').split('T')[0] || '—'}</td>
                    <td className="col-actions">
                      <button className="btn btn-primary icon-only" onClick={()=>{
                        // open local detail modal and also call parent navigation handler when present
                        setSelectedId(d.id);
                        pendingScrollId.current = d.id;
                        setModalOpen(true);
                        if (onOpenDocument) onOpenDocument(d);
                      }} title="Visualizar">
                        <EyeIcon width={16} height={16} stroke="#fff" />
                      </button>
                      <a className="btn btn-icon" href={`${API_URL}/api/v1/documents/${d.id}/download`} title="Baixar">
                        <DownloadIcon width={16} height={16} stroke="#0f172a" />
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
        {modalOpen && <DocumentModal docId={selectedId} onClose={()=>setModalOpen(false)} />}
    </div>
  );
}
