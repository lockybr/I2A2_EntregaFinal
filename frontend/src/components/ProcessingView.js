function ProcessingView({ docs }) {
  // ...existing code...
  return (
    <div className="processing-view">
      <div style={{marginBottom: 8, fontSize: 14, color: '#888'}}>
        <b>docId:</b> {docs && docs[0] ? docs[0] : 'N/A'} | <b>Polling:</b> {pollTries} tentativas
      </div>
      <h2>⚡ Pipeline de Processamento</h2>
      <div className="pipeline">
        {PIPELINE_STEPS.map((step) => (
          <div 
            key={step.id}
            className={`pipeline-step ${currentStep >= step.id ? 'active' : ''} ${currentStep === step.id ? 'current' : ''}`}
          >
            <div className="step-icon">{step.icon}</div>
            <div className="step-name">{step.name}</div>
                            {((!parsedData || Object.values(parsedData).every(
                              v => v == null || v === '-' || (typeof v === 'object' && Object.values(v).every(x => x == null || x === '-'))
                            )) && results.ocr_text) ? (
                              <div className="ocr-raw-text">
                                <h4>📝 Texto Bruto Extraído</h4>
                                <pre style={{background:'#f8fafc',padding:'1rem',borderRadius:8,border:'1px solid #e2e8f0',color:'#334155',fontSize:'1rem',maxHeight:300,overflow:'auto'}}>{results.ocr_text}</pre>
                              </div>
                            ) : (
                              <div className="extracted-data-wrapper">
                                <div className="data-grid">
                                  {/* Emitente */}
                                  <div className="data-item"><span className="data-label">Emitente - Razão Social:</span><span className="data-value">{parsedData?.emitente?.nome || parsedData?.emitente?.razao_social || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Emitente - CNPJ/CPF:</span><span className="data-value">{parsedData?.emitente?.cnpj || parsedData?.emitente?.cpf || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Emitente - Inscrição Estadual:</span><span className="data-value">{parsedData?.emitente?.inscricao_estadual || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Emitente - Endereço:</span><span className="data-value">{parsedData?.emitente?.endereco || '-'}</span></div>
                                  {/* Destinatário */}
                                  <div className="data-item"><span className="data-label">Destinatário - Razão Social:</span><span className="data-value">{parsedData?.destinatario?.nome || parsedData?.destinatario?.razao_social || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Destinatário - CNPJ/CPF:</span><span className="data-value">{parsedData?.destinatario?.cnpj || parsedData?.destinatario?.cpf || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Destinatário - Inscrição Estadual:</span><span className="data-value">{parsedData?.destinatario?.inscricao_estadual || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Destinatário - Endereço:</span><span className="data-value">{parsedData?.destinatario?.endereco || '-'}</span></div>
                                  {/* Outros elementos */}
                                  <div className="data-item"><span className="data-label">Número da Nota:</span><span className="data-value">{parsedData?.outros?.numero_nota || parsedData?.outros?.numero_nf || parsedData?.numero_nota || parsedData?.numero_nf || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Chave de Acesso:</span><span className="data-value">{parsedData?.outros?.chave_acesso || parsedData?.chave_acesso || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Data de Emissão:</span><span className="data-value">{parsedData?.outros?.data_emissao || parsedData?.data_emissao || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Natureza da Operação:</span><span className="data-value">{parsedData?.outros?.natureza_operacao || parsedData?.natureza_operacao || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Forma de Pagamento:</span><span className="data-value">{parsedData?.outros?.forma_pagamento || parsedData?.forma_pagamento || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">Valor Total da Nota:</span><span className="data-value highlight">{parsedData?.outros?.valor_total || parsedData?.valor_total || '-'}</span></div>
                                  {/* Códigos fiscais */}
                                  <div className="data-item"><span className="data-label">CFOP:</span><span className="data-value">{parsedData?.codigos_fiscais?.cfop || parsedData?.cfop || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">CST:</span><span className="data-value">{parsedData?.codigos_fiscais?.cst || parsedData?.cst || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">NCM:</span><span className="data-value">{parsedData?.codigos_fiscais?.ncm || parsedData?.ncm || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">CSOSN:</span><span className="data-value">{parsedData?.codigos_fiscais?.csosn || parsedData?.csosn || '-'}</span></div>
                                  {/* Impostos */}
                                  <div className="data-item"><span className="data-label">ICMS - Alíquota:</span><span className="data-value">{parsedData?.impostos?.icms?.aliquota || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">ICMS - Base de Cálculo:</span><span className="data-value">{parsedData?.impostos?.icms?.base_calculo || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">ICMS - Valor:</span><span className="data-value">{parsedData?.impostos?.icms?.valor || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">IPI - Valor:</span><span className="data-value">{parsedData?.impostos?.ipi?.valor || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">PIS - Valor:</span><span className="data-value">{parsedData?.impostos?.pis?.valor || '-'}</span></div>
                                  <div className="data-item"><span className="data-label">COFINS - Valor:</span><span className="data-value">{parsedData?.impostos?.cofins?.valor || '-'}</span></div>
                                </div>
                                {/* Itens da nota fiscal */}
                                <div className="items-section">
                                  <h4>🛒 Itens da Nota</h4>
                                  {Array.isArray(parsedData?.itens) && parsedData.itens.length > 0 ? (
                                    <table className="items-table">
                                      <thead>
                                        <tr>
                                          <th>Descrição</th>
                                          <th>Quantidade</th>
                                          <th>Unidade</th>
                                          <th>Valor Unitário</th>
                                          <th>Valor Total</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {parsedData.itens.map((item, idx) => (
                                          <tr key={idx}>
                                            <td>{item.descricao || '-'}</td>
                                            <td>{item.quantidade || '-'}</td>
                                            <td>{item.unidade || '-'}</td>
                                            <td>{item.valor_unitario || '-'}</td>
                                            <td>{item.valor_total || '-'}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  ) : (
                                    <div className="no-items">Nenhum item encontrado.</div>
                                  )}
                                </div>
                                <div className="export-buttons">
                                  <button className="export-btn">📥 Exportar JSON</button>
                                  <button className="export-btn">📥 Exportar XML</button>
                                  <button className="export-btn">📥 Exportar CSV</button>
                                </div>
                              </div>
                                          <th>Valor Total</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {parsedData.itens.map((item, idx) => (
                                          <tr key={idx}>
                                            <td>{item.descricao || '-'}</td>
                                            <td>{item.quantidade || '-'}</td>
                                            <td>{item.unidade || '-'}</td>
                                            <td>{item.valor_unitario || '-'}</td>
                                            <td>{item.valor_total || '-'}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  ) : (
                                    <div className="no-items">Nenhum item encontrado.</div>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      );
                  <div className="data-item"><span className="data-label">Natureza da Operação:</span><span className="data-value">{parsedData?.outros?.natureza_operacao || parsedData?.natureza_operacao || '-'}</span></div>
                </div>
              )}
              <div className="export-buttons">
                <button className="export-btn">📥 Exportar JSON</button>
                <button className="export-btn">📥 Exportar XML</button>
                <button className="export-btn">📥 Exportar CSV</button>
              </div>
            </>
                {/* Outros elementos */}
                <div className="data-item"><span className="data-label">Número da Nota:</span><span className="data-value">{parsedData?.outros?.numero_nota || parsedData?.outros?.numero_nf || parsedData?.numero_nota || parsedData?.numero_nf || '-'}</span></div>
                <div className="data-item"><span className="data-label">Chave de Acesso:</span><span className="data-value">{parsedData?.outros?.chave_acesso || parsedData?.chave_acesso || '-'}</span></div>
                <div className="data-item"><span className="data-label">Data de Emissão:</span><span className="data-value">{parsedData?.outros?.data_emissao || parsedData?.data_emissao || '-'}</span></div>
                <div className="data-item"><span className="data-label">Natureza da Operação:</span><span className="data-value">{parsedData?.outros?.natureza_operacao || parsedData?.natureza_operacao || '-'}</span></div>
              </div>
            )}
              <div className="data-item"><span className="data-label">Forma de Pagamento:</span><span className="data-value">{parsedData?.outros?.forma_pagamento || parsedData?.forma_pagamento || '-'}</span></div>
              <div className="data-item"><span className="data-label">Valor Total da Nota:</span><span className="data-value highlight">{parsedData?.outros?.valor_total || parsedData?.valor_total || '-'}</span></div>
              {/* Códigos fiscais */}
              <div className="data-item"><span className="data-label">CFOP:</span><span className="data-value">{parsedData?.codigos_fiscais?.cfop || parsedData?.cfop || '-'}</span></div>
              <div className="data-item"><span className="data-label">CST:</span><span className="data-value">{parsedData?.codigos_fiscais?.cst || parsedData?.cst || '-'}</span></div>
              <div className="data-item"><span className="data-label">NCM:</span><span className="data-value">{parsedData?.codigos_fiscais?.ncm || parsedData?.ncm || '-'}</span></div>
              <div className="data-item"><span className="data-label">CSOSN:</span><span className="data-value">{parsedData?.codigos_fiscais?.csosn || parsedData?.csosn || '-'}</span></div>
              {/* Impostos */}
              <div className="data-item"><span className="data-label">ICMS - Alíquota:</span><span className="data-value">{parsedData?.impostos?.icms?.aliquota || '-'}</span></div>
              <div className="data-item"><span className="data-label">ICMS - Base de Cálculo:</span><span className="data-value">{parsedData?.impostos?.icms?.base_calculo || '-'}</span></div>
              <div className="data-item"><span className="data-label">ICMS - Valor:</span><span className="data-value">{parsedData?.impostos?.icms?.valor || '-'}</span></div>
              <div className="data-item"><span className="data-label">IPI - Valor:</span><span className="data-value">{parsedData?.impostos?.ipi?.valor || '-'}</span></div>
              <div className="data-item"><span className="data-label">PIS - Valor:</span><span className="data-value">{parsedData?.impostos?.pis?.valor || '-'}</span></div>
              <div className="data-item"><span className="data-label">COFINS - Valor:</span><span className="data-value">{parsedData?.impostos?.cofins?.valor || '-'}</span></div>
            </div>
            {/* Itens da nota fiscal */}
            <div className="items-section">
              <h4>🛒 Itens da Nota</h4>
              {Array.isArray(parsedData?.itens) && parsedData.itens.length > 0 ? (
                <table className="items-table">
                  <thead>
                    <tr>
                      <th>Descrição</th>
                      <th>Quantidade</th>
                      <th>Unidade</th>
                      <th>Valor Unitário</th>
                      <th>Valor Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsedData.itens.map((item, idx) => (
                      <tr key={idx}>
                        <td>{item.descricao || '-'}</td>
                        <td>{item.quantidade || '-'}</td>
                        <td>{item.unidade || '-'}</td>
                        <td>{item.valor_unitario || '-'}</td>
                        <td>{item.valor_total || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="no-items">Nenhum item encontrado.</div>
              )}
            </div>
          </div>
          <div className="export-buttons">
            <button className="export-btn">📥 Exportar JSON</button>
            <button className="export-btn">📥 Exportar XML</button>
            <button className="export-btn">📥 Exportar CSV</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProcessingView;
