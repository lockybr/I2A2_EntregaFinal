import React, {useEffect, useState} from 'react';
import axios from 'axios';
import './ProcessingView.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function DocumentModal({docId, onClose}){
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(()=>{
    if (!docId) { setDoc(null); return; }
    let mounted = true;
    setLoading(true);
    axios.get(`${API_URL}/api/v1/documents/${docId}/results`).then(res=>{
      if (!mounted) return;
      setDoc(res.data || null);
    }).catch(e=>{
      if (!mounted) return;
      setDoc({ error: String(e) });
    }).finally(()=>{ if (mounted) setLoading(false); });
    return ()=>{ mounted = false; };
  }, [docId]);

  if (!docId) return null;

  const ed = doc?.extracted_data || {};
  const itens = Array.isArray(ed?.itens) ? ed.itens : [];
  const impostos = ed?.impostos || {};
  const codes = ed?.codigos_fiscais || {};

  return (
    <div className="doc-modal-backdrop" onClick={onClose}>
      <div className="doc-modal" onClick={(e)=>e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="doc-modal-header">
          <h3>Detalhes do documento</h3>
          <div style={{display:'flex', gap:8, alignItems:'center'}}>
            <a className="download-btn" href={`${API_URL}/api/v1/documents/${docId}/download`} target="_blank" rel="noreferrer">Baixar</a>
            <button className="btn btn-ghost" onClick={onClose}>Fechar</button>
          </div>
        </div>
        <div className="doc-modal-body">
          {loading && <div>Carregando...</div>}
          {!loading && doc && doc.error && <div className="error">Erro: {doc.error}</div>}
          {!loading && doc && !doc.error && (
            <div className="doc-details">
              <div className="results-header">
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:12}}>
                  <div>
                    <div style={{fontWeight:700}}>{doc.filename}</div>
                    <div style={{color:'#64748b', fontSize:'0.9rem'}}>{(doc.uploaded_at||'').replace('T',' ').split('.')[0]}</div>
                  </div>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontWeight:700}}>{doc.status} {doc.progress? `(${doc.progress}%)` : ''}</div>
                    <div style={{color:'#64748b'}}>Valor total: R$ {doc.aggregates?.valor_total_calc ?? '—'}</div>
                  </div>
                </div>
              </div>

              <div className="section-grid" style={{marginTop:12}}>
                <div className="card">
                  <label>Emitente</label>
                  <div className="value">{ed?.emitente?.razao_social || '—'}</div>
                  <div className="data-item"><span className="data-label">CNPJ:</span> <span className="data-value monospace">{ed?.emitente?.cnpj || '—'}</span></div>
                  <div className="data-item"><span className="data-label">Inscrição Estadual:</span> <span className="data-value">{ed?.emitente?.inscricao_estadual || '—'}</span></div>
                  <div className="data-item"><span className="data-label">Endereço:</span> <div className="data-value">{ed?.emitente?.endereco || '—'}</div></div>
                </div>
                <div className="card">
                  <label>Destinatário</label>
                  <div className="value">{ed?.destinatario?.razao_social || '—'}</div>
                  <div className="data-item"><span className="data-label">CNPJ/CPF:</span> <span className="data-value monospace">{ed?.destinatario?.cnpj || '—'}</span></div>
                  <div className="data-item"><span className="data-label">Inscrição Estadual:</span> <span className="data-value">{ed?.destinatario?.inscricao_estadual || '—'}</span></div>
                  <div className="data-item"><span className="data-label">Endereço:</span> <div className="data-value">{ed?.destinatario?.endereco || '—'}</div></div>
                </div>
              </div>

              <div style={{marginTop:16}} className="items-section">
                <h4>Itens</h4>
                {itens.length ? (
                  <div className="items-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Descrição</th>
                          <th>Quantidade</th>
                          <th>Unidade</th>
                          <th>Valor Unit.</th>
                          <th>Valor Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {itens.map((it, idx)=>(
                          <tr key={idx}>
                            <td style={{maxWidth:420}}>{it.descricao || '—'}</td>
                            <td>{it.quantidade ?? '—'}</td>
                            <td>{it.unidade || '—'}</td>
                            <td>{it.valor_unitario ?? '—'}</td>
                            <td>{it.valor_total ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <div className="no-items">Nenhum item identificado</div>}
              </div>

              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginTop:16}}>
                <div className="card">
                  <label>Impostos</label>
                  <div className="data-item"><span className="data-label">ICMS (valor):</span> <span className="data-value">{impostos?.icms?.valor ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">ICMS (aliquota):</span> <span className="data-value">{impostos?.icms?.aliquota ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">IPI:</span> <span className="data-value">{impostos?.ipi?.valor ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">PIS:</span> <span className="data-value">{impostos?.pis?.valor ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">COFINS:</span> <span className="data-value">{impostos?.cofins?.valor ?? '—'}</span></div>
                </div>
                <div className="card">
                  <label>Códigos fiscais</label>
                  <div className="data-item"><span className="data-label">CFOP:</span> <span className="data-value">{codes?.cfop ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">CST:</span> <span className="data-value">{codes?.cst ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">NCM:</span> <span className="data-value">{codes?.ncm ?? '—'}</span></div>
                  <div className="data-item"><span className="data-label">CSOSN:</span> <span className="data-value">{codes?.csosn ?? '—'}</span></div>
                </div>
              </div>

              <div style={{marginTop:16}} className="section-grid">
                <div className="card">
                  <label>Número da nota</label>
                  <div className="value monospace">{ed?.numero_nota || '—'}</div>
                </div>
                <div className="card">
                  <label>Chave de acesso</label>
                  <div className="value access-key">{ed?.chave_acesso || '—'}</div>
                </div>
                <div className="card">
                  <label>Data de emissão</label>
                  <div className="value">{ed?.data_emissao || '—'}</div>
                </div>
                <div className="card">
                  <label>Natureza da operação</label>
                  <div className="value">{ed?.natureza_operacao || '—'}</div>
                </div>
                <div className="card">
                  <label>Forma de pagamento</label>
                  <div className="value">{ed?.forma_pagamento || '—'}</div>
                </div>
                <div className="card">
                  <label>Valor total impostos</label>
                  <div className="value">R$ {ed?.valor_total_impostos ?? '—'}</div>
                </div>
              </div>

              <div style={{marginTop:16}}>
                <details>
                  <summary>OCR (preview)</summary>
                  <pre className="raw-text">{(doc.ocr_text||'')}</pre>
                </details>
              </div>

              <div style={{marginTop:12}}>
                <details>
                  <summary>Raw extracted (debug)</summary>
                  <pre className="raw-text">{JSON.stringify(doc.raw_extracted || doc.extracted_data || {}, null, 2)}</pre>
                </details>
              </div>

            </div>
          )}
        </div>
      </div>
    </div>
  );
}
