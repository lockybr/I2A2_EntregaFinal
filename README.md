# Sistema Inteligente de Extração de Dados Fiscais

![](https://img.shields.io/badge/version-1.0.0-blue.svg)
![](https://img.shields.io/badge/python-3.11-blue.svg)
![](https://img.shields.io/badge/react-18-blue.svg)

Este repositório contém um sistema completo para extração automatizada de informações fiscais a partir de documentos (PDF, imagens, XML, cupons). O projeto combina OCR, heurísticas, agentes especializados e uma camada de LLM para enriquecer e normalizar os dados extraídos.

Principais objetivos
- Receber uploads de documentos fiscais (PDF, imagens, XML, CSV/Texto).
- Extrair texto com OCR quando necessário e, quando possível, aproveitar texto selecionável do PDF.
- Rodar agentes heurísticos e um LLM (opcional, via OpenRouter) para estruturar campos fiscais (emitente, destinatário, itens, impostos, totais, chave de acesso, etc.).
- Normalizar, computar agregados (valor_total_calc, impostos) e persistir um registro leve por documento.
- Fornecer uma UI para acompanhar uploads, status do pipeline e inspecionar os resultados.

Documentação completa e detalhada está na pasta `docs/` neste repositório. Consulte os seguintes arquivos:

- `docs/ARCHITECTURE.md` — visão geral da arquitetura, diagrama de componentes, fluxo e operações de manutenção.
- `docs/AGENTS.md` — descrição pormenorizada de cada agente (`ocr_agent`, `nlp_agent`, `enrichment_agent`, etc.).

Recomendo abrir esses arquivos para entender o desenho de módulos e o fluxo de dados.

## 🚀 Quick start (dev)

Requisitos mínimos
- Python 3.10+ (recomendado 3.11)
- Node.js 16+ / npm
- Tesseract OCR (instale localmente no host e aponte `TESSERACT_CMD` se necessário)

Execução local (passos mínimos)

Backend (PowerShell exemplo)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Se necessário, aponte Tesseract: $env:TESSERACT_CMD = 'C:\path\to\tesseract.exe'
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend

```powershell
cd frontend
npm install
npm start
```

## API (endpoints principais)
- POST /api/v1/documents/upload — envia um ou múltiplos arquivos; retorna IDs criados e agenda processamento em background.
- GET /api/v1/documents — lista documentos com metadados resumidos (status, progress, aggregates, preview de ocr/raw_extracted).
- GET /api/v1/documents/{id}/results — retorna o registro completo do documento (extracted_data, ocr_text, raw_extracted, aggregates, status).
- GET /api/v1/documents/{id}/download — baixa o arquivo original enviado.
- POST /api/v1/documents/{id}/enrich — força reexecução das heurísticas de enriquecimento em um documento específico.
- POST /api/v1/admin/recompute_aggregates — recomputa agregados para todos os documentos a partir do campo `extracted_data`.
- POST /api/v1/admin/reload_db — recarrega o DB de disco para memória (útil após restaurar `backend/api/documents_db.json`).
- GET /api/v1/admin/db_info — mostra caminho e preview do arquivo `documents_db.json` usado pelo processo.

## Componentes e agentes

Backend (local, leve):
- FastAPI — servidor HTTP da API.
- Persistência: um arquivo JSON atômico em `backend/api/documents_db.json` (a persistência é deliberadamente simples para facilitar deploys e debugging).

Agentes (dentro de `backend/agents`):
- `ocr_agent.py` — funções utilitárias e wrappers para Tesseract/pdf2image/extract_text.
- `nlp_agent.py` — helper e regras de NER / limpeza de texto.
- `specialist_agent.py` — heurísticas para detectar seção de produtos e extrair linhas de itens (multi-linha, quantidades, preços).
- `enrichment_agent.py` — composição de heurísticas, regex e llamadas ao especialista/LLM para preencher campos faltantes.
- `validation_agent.py` — regras fiscais básicas e validação de formatos (CNPJ, chave NF-e, datas).
- `retrieval_agent.py` e `reporting_agent.py` — utilitários para busca simples e geração de relatórios.

LLM integration
- O sistema pode usar OpenRouter (via variável `OPENROUTER_API_KEY`) para chamadas de LLM. Se não houver chave válida, o fluxo usa heurísticas locais e LLM é desabilitado sem interromper o processamento.

Pipeline (por documento)
1. ingestao — grava o upload e agenda o processamento.
2. preprocessamento — tenta extrair texto selecionável de PDFs (PyPDF2/pdfminer).
3. ocr — usa Tesseract se não houver texto selecionável.
4. nlp — LLM e heurísticas tentam transformar texto em JSON estruturado.
5. validacao — aplica regras e normalizações.
6. finalizado — computa agregados, marca `status: finalizado` e persiste.

## Mudanças recentes nesta branch
- O front-end agora mostra "Processamentos" (no menu) e traz um modo onde múltiplos uploads mostram uma "Lista de Processamentos" com atualização em tempo real. Quando o primeiro documento terminar de processar após um upload múltiplo, o sistema abre automaticamente a visualização detalhada para esse documento.

## Limpeza e manutenção
- Arquivos fonte não usados foram removidos ou marcados como deprecados para reduzir confusão. O armazenamento principal continua sendo o JSON simples em `backend/api`.
- Instalação via Docker ou containers não faz parte desta entrega. Todos os arquivos de configuração de container foram removidos.

## Documentação e arquitetura
- Veja `docs/ARCHITECTURE.md` para um diagrama textual (ASCII/PlantUML) e explicação dos módulos, responsabilidades e fluxo de dados.

## Contribuindo
- Abra issues para bugs ou melhorias. Para PRs, siga o padrão: branch com descrição curta, testes mínimos e atualize `docs/ARCHITECTURE.md` se a arquitetura mudar.

## Licença
MIT
