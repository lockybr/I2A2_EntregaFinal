import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Dashboard.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function smallNumber(n) {
  if (n == null) return '—';
  if (typeof n === 'number') return n.toLocaleString('pt-BR');
  return String(n);
}

function StatusBar({counts}){
  const total = Object.values(counts).reduce((s,v)=>s+v,0) || 1;
  const keys = Object.keys(counts);
  return (
    <div className="status-bar">
      {keys.map(k=>{
        const v = counts[k]||0;
        const pct = Math.round((v/total)*100);
        return (
          <div key={k} className="status-seg" title={`${k}: ${v}`} style={{flex: v}}>
            <div className="seg-label">{k} <strong>{v}</strong></div>
            <div className="seg-pct">{pct}%</div>
          </div>
        );
      })}
    </div>
  );
}

function BarChart({labels, values, height=140, color='#4f46e5'}){
  const max = Math.max(...values, 1);
  return (
    <div className="bar-chart" style={{height}}>
      {values.map((v,i)=>{
        const pct = Math.round((Number(v)/max)*100);
        return (
          <div key={i} className="bar-item">
            <div className="bar" style={{height: `${pct}%`, background: color}} title={`${labels[i]}: ${v}`} />
            <div className="bar-label">{labels[i]}</div>
          </div>
        );
      })}
    </div>
  );
}

function PieChart({labels, values, colors=['#60a5fa','#34d399','#f59e0b','#ef4444','#a78bfa'], size=160}){
  const total = values.reduce((s,v)=>s+Number(v||0),0);
  if (!total) return <div className="loading">Sem dados para o gráfico</div>;
  // build conic-gradient stops using percentages
  let accum = 0;
  const stops = values.map((v,i)=>{
    const pct = Math.round((Number(v||0)/total)*10000)/100; // two decimals
    const start = accum;
    const end = accum + pct;
    accum = end;
    return `${colors[i % colors.length]} ${start}% ${end}%`;
  }).join(', ');
  const bg = `conic-gradient(${stops})`;
  return (
    <div className="pie-chart-box">
      <div className="pie-chart" style={{width:size, height:size, background:bg}} />
      <div className="pie-legend">
        {labels.map((l,i)=> (
          <div key={i} className="pie-legend-item">
            <span className="swatch" style={{background: colors[i % colors.length]}} />
            <span className="legend-label">{l}</span>
            <span className="legend-value">R$ {smallNumber(Math.round(Number(values[i]||0)*100)/100)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Dashboard() {
  const [docs, setDocs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');

  useEffect(()=>{ fetchDocs(); }, []);

  const fetchDocs = async () => {
    setLoading(true);
    try{
      const res = await axios.get(`${API_URL}/api/v1/documents`);
      const list = res.data?.documents || [];
      setDocs(list);
    }catch(e){
      console.error('Erro carregando documentos:', e.message || e);
      setDocs([]);
    }finally{ setLoading(false); }
  };

  if (loading) return <div className="loading">Carregando métricas...</div>;

  // apply filters
  const docsFiltered = (docs || []).filter(d => {
    if (filterStatus && filterStatus !== 'all'){
      const s = (d.status||'').toString().toLowerCase();
      if (filterStatus === 'finalizado' && !(s==='finalizado' || s==='done' || s==='completed')) return false;
      if (filterStatus === 'erro' && !(s==='erro' || s==='error' || s==='failed')) return false;
      if (filterStatus === 'processing' && (s==='finalizado' || s==='erro' || s==='done' || s==='error' || s==='failed' || s==='completed')) return false;
    }
    if ((filterFrom || filterTo)){
      const date = (d.uploaded_at || d.created_at || '').split('T')[0];
      if (filterFrom && date && date < filterFrom) return false;
      if (filterTo && date && date > filterTo) return false;
    }
    return true;
  });

  // compute metrics
  const total = docsFiltered.length;
  const byStatus = docsFiltered.reduce((acc,d)=>{ const s=(d.status||'unknown').toLowerCase(); acc[s]=(acc[s]||0)+1; return acc; },{});
  const finalizado = byStatus['finalizado']||byStatus['done']||byStatus['completed']||0;
  const erro = byStatus['erro']||byStatus['error']||byStatus['failed']||0;
  const processing = total - finalizado - erro;
  // sum valor_total where present
  // sum valor_total if present, otherwise sum item totals
  const parseNum = (v) => {
    if (v == null) return NaN;
    if (typeof v === 'number') return v;
    const s = String(v).replace(/[^0-9,.-]/g,'').replace(/\./g,'').replace(/,/g,'.');
    const n = parseFloat(s);
    return isNaN(n) ? NaN : n;
  };

  // Prefer server-side aggregates when available (valor_total_calc), otherwise fall back to extracted_data
  const sumValor = docsFiltered.reduce((s,d)=>{
    const aggVal = d?.aggregates?.valor_total_calc;
    if (aggVal != null) return s + Number(aggVal || 0);
    const v = d?.extracted_data?.valor_total;
    const n = parseNum(v);
    if (!isNaN(n)) return s + n;
    // fallback: sum itens.valor_total
    const items = d?.extracted_data?.itens || [];
    const itemsSum = items.reduce((isum,it)=>{ const iv = parseNum(it?.valor_total); return isum + (isNaN(iv)?0:iv); }, 0);
    return s + itemsSum;
  },0);

  // top emitentes
  const byEmit = {};
  for (const d of docsFiltered){
    const name = d?.extracted_data?.emitente?.razao_social || d?.extracted_data?.emitente?.nome || 'Sem Emitente';
    byEmit[name] = (byEmit[name]||0)+1;
  }
  const topEmit = Object.entries(byEmit).sort((a,b)=>b[1]-a[1]).slice(0,6);

  // trend by date (uploaded_at or created_at) grouped by day
  const byDay = {};
  for (const d of docsFiltered){
    const raw = (d.uploaded_at || d.created_at || d.created || '');
    const dt = raw ? raw.split('T')[0] : null;
    const key = dt || 'unknown';
    byDay[key] = (byDay[key]||0)+1;
  }
  // prefer real dates only (exclude 'unknown') and sort chronologically
  const trendLabels = Object.keys(byDay).filter(k=>k && k !== 'unknown').sort();
  const trendValues = trendLabels.map(k=> Number(byDay[k]||0));

  // aggregate taxes for pie chart
  const taxKeys = ['icms','ipi','pis','cofins'];
  const taxesAgg = {};
  for (const key of taxKeys) taxesAgg[key] = 0;
  for (const d of docsFiltered){
    // prefer server-side aggregates for impostos
    const aggImp = d?.aggregates?.impostos_calc || null;
    const imp = aggImp ? aggImp : (d?.extracted_data?.impostos || {});
    const text = String(d?.raw_extracted || d?.ocr_text || '');
    for (const k of taxKeys){
      let val = imp[k]?.valor ?? imp[k];
      let n = parseNum(val);
      // if not present or NaN/zero, try to extract from OCR/raw text (simple heuristics)
      if ((n === undefined || n === null || isNaN(n) || n === 0) && text){
        try{
          const re = new RegExp(k.toUpperCase() + "[^\\n\\r:\\-]*[:\\-]?[^\\n\\r]*?([0-9]{1,3}(?:[.,][0-9]{2})?)","i");
          const m = text.match(re);
          if (m && m[1]){
            n = parseNum(m[1]);
          }
          // fallback: look for 'Vlr Aprox dos Tributos' pair Federal/Estadual
          if ((n === undefined || n === null || isNaN(n) || n === 0)){
            const pair = text.match(/Vlr\s*Aprox[\s\S]*?([0-9.,]+)\s*Federal\s*\/?\s*R?\$?\s*([0-9.,]+)\s*Estad/i);
            if (pair){
              const fed = parseNum(pair[1]);
              const est = parseNum(pair[2]);
              if (k === 'icms' && est != null) n = est;
              if ((k === 'pis' || k === 'cofins') && fed != null) {
                // split federal as heuristic
                n = Math.round(((fed/2) || 0)*100)/100;
              }
            }
          }
        }catch(e){ /* ignore */ }
      }
      taxesAgg[k] += (isNaN(n)?0:n);
    }
  }
  const taxesSum = Object.values(taxesAgg).reduce((s,v)=>s+(isNaN(v)?0:v),0);
  const remaining = Math.max(0, sumValor - taxesSum);
  const pieLabels = ['Outros'].concat(taxKeys.map(k=>k.toUpperCase()));
  const pieValues = [remaining].concat(taxKeys.map(k=>taxesAgg[k]));

  return (
    <div className="dashboard">
      <div className="dash-header">
        <h2>📊 Dashboard Executivo</h2>
        <div className="dash-actions">
          <button onClick={fetchDocs}>↻ Atualizar</button>
          <label style={{marginLeft:8}}>Status:
            <select value={filterStatus} onChange={e=>setFilterStatus(e.target.value)} style={{marginLeft:6}}>
              <option value="all">Todos</option>
              <option value="finalizado">Finalizado</option>
              <option value="processing">Em processamento</option>
              <option value="erro">Erro</option>
            </select>
          </label>
          <label style={{marginLeft:8}}>De: <input type="date" value={filterFrom} onChange={e=>setFilterFrom(e.target.value)} /></label>
          <label style={{marginLeft:8}}>Até: <input type="date" value={filterTo} onChange={e=>setFilterTo(e.target.value)} /></label>
          <button onClick={() => { const csv = ['metric,value','total_documents,'+total,'finalizado,'+finalizado,'erro,'+erro,'processing,'+processing,'sum_valor_total,'+sumValor.toFixed(2)].join('\n'); const b=new Blob([csv],{type:'text/csv'}); const u=URL.createObjectURL(b); const a=document.createElement('a'); a.href=u; a.download='metrics.csv'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(u); }}>📥 Exportar métricas</button>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon">📄</div>
          <div className="metric-value">{smallNumber(total)}</div>
          <div className="metric-label">Documentos</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">✅</div>
          <div className="metric-value">{smallNumber(finalizado)}</div>
          <div className="metric-label">Finalizados</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">⚠️</div>
          <div className="metric-value">{smallNumber(erro)}</div>
          <div className="metric-label">Erros</div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">💰</div>
          <div className="metric-value">R$ {smallNumber(Math.round(sumValor*100)/100)}</div>
          <div className="metric-label">Soma Valor Total</div>
        </div>
      </div>

      <div style={{marginTop:10, display:'flex', gap:12}}>
        <div style={{flex:1}}>
          <h4>Top Emitentes (por quantidade)</h4>
          <ul className="top-emit">
            {topEmit.map(([name,c],i)=> (<li key={i}><strong>{c}</strong> — {name}</li>))}
          </ul>
        </div>
        <div style={{width:320}}>
          <h4>Top Emitentes (por valor)</h4>
          <ul className="top-emit">
            {Object.entries(docsFiltered.reduce((acc,d)=>{ const name = d?.extracted_data?.emitente?.razao_social || d?.extracted_data?.emitente?.nome || 'Sem Emitente'; const v = d?.extracted_data?.valor_total; const n = typeof v==='number'? v : (typeof v==='string'? parseFloat(String(v).replace(/[^0-9.,-]/g,'').replace(/\./g,'').replace(/,/g,'.')):0); acc[name]=(acc[name]||0)+ (isNaN(n)?0:n); return acc; },{})).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([name,v])=>(<li key={name}><strong>R$ {smallNumber(Math.round(v*100)/100)}</strong> — {name}</li>))}
          </ul>
        </div>
      </div>

      <h3>Status Overview</h3>
      <StatusBar counts={byStatus} />

      <div className="charts-row">
        <div className="chart-card">
          <h4>Trend (por dia)</h4>
          {trendLabels.length ? <BarChart labels={trendLabels} values={trendValues} /> : <div className="loading">Sem dados de tendência</div>}
        </div>
        <div className="chart-card">
          <h4>Distribuição: Total vs Impostos</h4>
          <PieChart labels={pieLabels} values={pieValues} />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
