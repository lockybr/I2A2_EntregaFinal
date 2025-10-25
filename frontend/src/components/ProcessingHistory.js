import React, {useEffect, useState} from 'react';
import axios from 'axios';
import './Dashboard.css';

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

export default function ProcessingHistory({onOpenDocument}){
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(()=>{ fetch(); }, []);

  const fetch = async ()=>{
    setLoading(true);
    try{
      const res = await axios.get(`${API_URL}/api/v1/documents`);
      setDocs(res.data?.documents || []);
    }catch(e){
      console.error('Erro ao carregar histórico', e.message||e);
      setDocs([]);
    }finally{ setLoading(false); }
  };

  if (loading) return <div className="loading">Carregando histórico...</div>;

  return (
    <div className="dashboard">
      <div className="dash-header">
        <h2>📚 Histórico de Processamento</h2>
        <div className="dash-actions">
          <button className="btn" onClick={fetch} title="Atualizar histórico">↻ Atualizar</button>
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
                <th>Data</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {docs.map(d=>{
                const val = d?.extracted_data?.valor_total ?? d?.aggregates?.valor_total_calc ?? '';
                const emit = d?.extracted_data?.emitente?.razao_social || d?.extracted_data?.emitente?.nome || '';
                const ts = (d.uploaded_at || d.created_at || '').replace('T',' ').split('.')[0] || '';
                const filename = d.filename || d.id;
                const label = `${filename}${ts? ' — ' + ts : ''} — ${d.id}`;
                return (
                  <tr key={d.id} className="history-row">
                    <td className="col-file" title={label}>
                      <div className="file-cell">
                        <div className="file-name">{filename}</div>
                        <div className="file-sub">{ts} • {d.id.slice(0,8)}</div>
                      </div>
                    </td>
                    <td className="col-status"><StatusBadge status={d.status} /></td>
                    <td className="col-value">R$ {formatCurrency(val)}</td>
                    <td className="col-emitente">{emit || '—'}</td>
                    <td className="col-date">{(d.uploaded_at || d.created_at || '').split('T')[0] || '—'}</td>
                    <td className="col-actions">
                      <button className="btn btn-primary" onClick={()=>{ if (onOpenDocument) onOpenDocument(d); }} title="Visualizar">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 5v14M19 12H5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        <span>Visualizar</span>
                      </button>
                      <a className="btn btn-icon" href={`${API_URL}/api/v1/documents/${d.id}/download`} title="Baixar">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="#0f172a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/><path d="M7 10l5 5 5-5" stroke="#0f172a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/><path d="M12 15V3" stroke="#0f172a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
