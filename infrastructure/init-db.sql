-- Schema do banco de dados PostgreSQL

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(50),
    file_size INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    confidence_score DECIMAL(5,2),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notas_fiscais (
    id SERIAL PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    numero VARCHAR(20) NOT NULL,
    serie VARCHAR(10),
    chave_acesso VARCHAR(44) UNIQUE,
    data_emissao DATE,
    valor_total DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emitentes (
    id SERIAL PRIMARY KEY,
    cnpj VARCHAR(18) UNIQUE NOT NULL,
    razao_social VARCHAR(200),
    inscricao_estadual VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_notas_chave ON notas_fiscais(chave_acesso);
CREATE INDEX idx_emitentes_cnpj ON emitentes(cnpj);

-- Dados de exemplo
INSERT INTO emitentes (cnpj, razao_social) VALUES
('12.345.678/0001-90', 'Empresa Exemplo LTDA'),
('98.765.432/0001-10', 'Fornecedor ABC LTDA');
