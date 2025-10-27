# Arquitetura do Sistema de Extração Fiscal

Esta documentação descreve em detalhes a arquitetura do projeto, o fluxo de dados, componentes principais, armazenamento, operações de manutenção e orientações para execução local e em produção. O conteúdo está em português (pt-BR).

## Visão Geral

O sistema é composto por um frontend (React) e um backend (FastAPI) que oferecem uma interface para upload, processamento assíncrono e inspeção de documentos fiscais (PDF, imagens, XML, CSV). O processamento usa uma combinação de heurísticas, agentes especializados e integração com modelos LLM (opcional, via OpenRouter) para extrair e normalizar campos fiscais.

Principais responsabilidades:
- Frontend: interface de upload, lista de processamentos, visualização detalhada de resultados.
- Backend API: recebimento de uploads, fila de processamento (background tasks), agentes de processamento (OCR, NLP, enrichment), persistência leve, endpoints de administração.

## Diagrama de componentes (Mermaid)

```mermaid
flowchart LR
  subgraph Frontend
    A[UI (React)] -->|POST /api/v1/documents/upload| B[Backend API]
    A -->|GET /api/v1/documents| B
    A -->|GET /api/v1/documents/{id}/results| B
  end

  subgraph Backend
    B --> C[Persistence (documents_db.json)]
    B --> D[Background Processor]
    D --> E[OCR Agent (Tesseract / pdf2image)]
    D --> F[NLP Agent (heuristics + LLM)]
    D --> G[Enrichment Agent]
    D --> H[Validation Agent]
    G --> F
  end

  subgraph External
    I[OpenRouter / LLM] -. optional .-> F
    J[Poppler / Tesseract Binaries] --> E
  end

  C -. backup/rotate .-> C_backup[(archives/)]
> Nota: a versão renderizável do diagrama (arquivo SVG) está disponível em `docs/assets/architecture.svg` — alguns ambientes não conseguem renderizar Mermaid diretamente; o SVG contém o diagrama sanitizado para visualização imediata.

![Arquitetura](/docs/assets/architecture.svg)
```

## Fluxo de processamento (por documento)

1. Ingestão
   - O cliente envia um ou mais arquivos para POST /api/v1/documents/upload.
   - O backend grava um registro mínimo em memória + persistência, define status `ingestao` e agenda a tarefa de processamento em background (FastAPI BackgroundTasks).

2. Pré-processamento
   - O pipeline tenta extrair texto selecionável do PDF usando PyPDF2 ou pdfminer.six.
   - Se houver texto selecionável, este é usado diretamente (mais fiable que OCR).

3. OCR
   - Caso não haja texto selecionável, o sistema usa pdf2image + Tesseract (pytesseract) para extrair texto de imagens.
   - O caminho do executável Tesseract pode ser ajustado por `TESSERACT_CMD` ou detectado automaticamente se instalado no sistema.

4. NLP / LLM
   - O texto resultante é passado para o agente NLP que aplica um prompt e, opcionalmente, chama o LLM via OpenRouter (configurado por `OPENROUTER_API_KEY`).
   - Há uma série de proteções: sondagem no startup para verificar a chave, lista rotativa de modelos 'free' como fallback, e tentativa de fallback heurístico caso o LLM falhe.

5. Enriquecimento
   - O `enrichment_agent` aplica heurísticas especializadas (regex, heurísticas fiscalizadas) para preencher campos faltantes e harmonizar formatos.

6. Validação e agregados
   - O `validation_agent` aplica regras básicas (CNPJ, formatos de chave NF-e, datas) e o backend computa agregados (soma de itens, impostos) usando `compute_aggregates`.

7. Finalização
   - O registro é marcado como `finalizado` e persistido.

## Dados e Persistência

- O armazenamento principal é um arquivo JSON atômico: `backend/api/documents_db.json`.
- A camada de persistência (`backend/api/persistence.py`) realiza gravação atômica (temp file + os.replace) e cria um backup simples `documents_db.json.bak` antes de substituir o arquivo principal.
- Em caso de corrupção do arquivo principal, o processo move o arquivo corrompido para `documents_db.json.corrupt_<ts>` e tenta recuperar a partir do `.bak` se disponível.
- Para permitir reinícios seguros, é possível sobrescrever o caminho do DB pela variável de ambiente `DOCUMENTS_DB_PATH`.

## Endpoints principais

- POST /api/v1/documents/upload — upload de arquivos, agenda processamento.
- GET /api/v1/documents — lista resumida dos documentos (status, progress, aggregates, previews).
- GET /api/v1/documents/{id}/results — registro completo do documento.
- GET /api/v1/documents/{id}/download — baixa o arquivo original.
- POST /api/v1/documents/{id}/enrich — executa enriquecimento manualmente para um documento específico.

Admin / manutenção
- POST /api/v1/admin/recompute_aggregates — recalcula agregados para todos os documentos.
- POST /api/v1/admin/reload_db — força recarregar o DB de disco para memória.
- POST /api/v1/admin/clear_db — faz backup (opcional) e substitui o DB por um vazio; limpa a store em memória.
- GET /api/v1/admin/db_info — mostra o caminho usado pelo processo e uma prévia do arquivo.

## Variáveis de ambiente importantes

- OPENROUTER_API_KEY — chave para OpenRouter (opcional). Sem essa chave o processamento continua usando heurísticas.
- DOCUMENTS_DB_PATH — caminho alternativo para o arquivo JSON de persistência. Útil para testes e recuperação.
- TESSERACT_CMD — caminho absoluto para o executável do Tesseract (sobrescreve detecção automática).
- POPPLER_PATH — caminho para binários poppler (usado por pdf2image no Windows).

## Operação local (PowerShell)

Exemplo para iniciar o backend apontando para um DB limpo:

```powershell
$env:DOCUMENTS_DB_PATH = "c:\labz\fiscal-extraction-system-COMPLETO\backend\api\documents_db.clean.json"
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (desenvolvimento):

```powershell
cd frontend
npm install
npm start
```

Ou com Docker Compose (o ambiente pode já incluir Tesseract/poppler):

```powershell
docker-compose up --build
```

## Boas práticas de manutenção

- Nunca delete os arquivos em `backend/api/archives/`; eles são backups e podem ser usados para restauração.
- Use `DOCUMENTS_DB_PATH` para apontar para um arquivo limpo durante recuperação.
- Evite executar múltiplos processos concorrentes usando o mesmo arquivo JSON sem um mecanismo de lock externo se estiver em produção.

## Limitações conhecidas

- Persistência baseada em JSON não é adequada para workloads concorrentes pesados ou para grandes volumes de dados (escalonar para uma DB relacional ou NoSQL é recomendado para produção).
- Dependência em binários locais (Tesseract, poppler) requer configuração no host; containers mitigam isso.
- Uso de LLMs via OpenRouter pode incorrer em latência, custos ou falhas de autenticação. O sistema trata isso com retries e fallbacks, mas resultados podem variar.

## Próximos passos sugeridos

- Adicionar scripts de migração/exportação para mover dados do JSON para um banco mais robusto.
- Implementar testes automatizados de integração para o pipeline de OCR->NLP->Enrichment.
- Adicionar métricas e observabilidade (Prometheus / logs estruturados) para monitorar falhas e tempo de processamento.

---
Arquivo gerado automaticamente pelo time de manutenção. Para dúvidas, abra uma issue.
# Fiscal Extraction System — Architecture and Documentation

Version: 1.0 (snapshot)
Date: 2025-10-26

This document explains the architecture, objectives, agents, orchestration, data flows, and operational instructions for the Fiscal Extraction System contained in this repository.

## Goal
The system ingests fiscal documents (PDF, image, XML, CSV), applies OCR and language-model-based extraction to identify invoice fields (emitente, destinatario, itens, impostos, valores, chave de acesso, etc.), enriches/normalizes the data with deterministic heuristics, and exposes an API + frontend dashboard for inspection, download and manual repair.

## High-level components
- backend/
  - `api/` — FastAPI application that exposes endpoints for upload, status, admin operations and runs the processing pipeline.
  - `agents/` — small modular agents responsible for specialized tasks: OCR/NLP enrichment, specialist heuristics for items and addresses, LLM helper.
  - `persistence` (module) — atomic save/load of `documents_db.json` to avoid truncation/corruption.
- frontend/
  - React application with views for uploading, viewing processing results, and an executive dashboard.
- scripts/
  - helper scripts to run local tests, reparations and sample processing for development.
- assets/
  - sample files (for local testing).

## Processing pipeline (high-level)
1. Upload (via frontend or `/api/v1/documents/upload`) — creates a `documents_db` record and schedules background `process_document`.
2. Preprocess/OCR: server tries to extract selectable text (PyPDF2/pdfminer) and falls back to image-based OCR (pytesseract + pdf2image) if necessary.
3. NLP / LLM extraction: a Chat-like prompt is sent to the configured LLM (OpenRouter-compatible) asking for a JSON object with standard fields. The system maintains a fallback/rotation list of free models to improve resilience.
4. Merge & Heuristics: LLM output is merged with deterministic heuristics (`simple_receipt_parser`) and passed to the `enrichment_agent` and `specialist_agent` for additional repairs.
5. Aggregation: numeric aggregates (`valor_total_calc`, `impostos_calc`) are computed from normalized fields and saved in the DB.
6. Persistence: records saved atomically to `backend/api/documents_db.json`.
7. Frontend periodically polls `/api/v1/documents` and `/api/v1/documents/{id}/results` to show status and data.

## Agents

### enrichment_agent
- Purpose: general heuristics and light-weight field extractions from textual sources (CNPJ, key, date, number heuristics, small-item heuristics when items absent). Also performs aggregate computation.
- Key features:
  - `find_cnpj`, `find_chave`, `find_date`, `find_money` — targeted regex-based extractors.
  - `compute_aggregates` — computes `valor_total_calc` respecting both top-level `valor_total` and sum(items); new policy prefers item-sum when items exist and differ significantly.
  - `enrich_record(record)` — main entry: fills missing fields, computes aggregates, calls `specialist_agent.refine_extracted`, then applies a final LLM-first verification for `valor_total` (via `llm_helper`) when there is disagreement between LLM-parsed top-level and items-sum.
- Decision policy: LLM-first — the LLM output is preferred when confident; otherwise a deterministic fallback is used and recorded.

### specialist_agent
- Purpose: domain heuristics for Brazilian fiscal documents (NF-e/DANFE, cupom, recibos) to extract structured items, NCM/CFOP, and detailed address components (bairro, município, UF, CEP) from noisy OCR text.
- Key functions:
  - `_find_product_section_lines(text)` — detect the product/item section from common markers or fallback to the last N lines.
  - `_extract_items_from_lines(lines)` — parse item descriptions, quantities, NCM, CFOP and monetary tokens.
  - `_extract_address_parts(addr)` — a focused address parser that returns a dict with `cep`, `uf`, `municipio`, `bairro`. It implements many heuristics and validations (valid UF checks, CEP normalizer, plausibility checks)
  - `refine_extracted(record, extracted)` — main entry: attempts to repair item lists, fill missing NCM/CFOP, and extract address parts. The function now also performs a full-text fallback scan across OCR/raw_extracted to find additional address-like lines and populate missing address fields.

### llm_helper
- Purpose: small helper to query an OpenRouter-compatible ChatCompletions endpoint to perform focused verification tasks (e.g., confirm whether to use the LLM top-level `valor_total` or the computed items-sum).
- Behavior: best-effort; if environment lacks an OpenRouter key (`OPENROUTER_API_KEY`), it returns a structured failure and the pipeline falls back to deterministic heuristics.

## Orchestration
- The HTTP API (`backend/api/main.py`) is the orchestrator for uploads and background processing.
- `process_document(doc_id, tmp_path, file_name)` runs the full pipeline for a single file and persists the document along the way (status updates: ingestao -> preprocessamento -> ocr -> nlp -> validacao -> finalizado).
- `enrich_record` is callable as an API endpoint (`/api/v1/documents/{doc_id}/enrich`) to re-run heuristics on stored records if corrections are needed.
- Admin endpoints added:
  - `/api/v1/admin/repair_from_raw` — re-parse `raw_extracted` JSON and replace `extracted_data` when the raw LLM output is richer.
  - `/api/v1/admin/recompute_aggregates` — recompute aggregates for all stored documents (helpful after changing aggregation logic).

## Data model (per document)
- id, filename, uploaded_at, status, progress
- tmp_path (path to uploaded file on disk)
- ocr_text (string)
- raw_file (optional text of the original file for debugging)
- raw_extracted (LLM output raw string)
- extracted_data (normalized JSON object)
- aggregates: { valor_total_calc: number, impostos_calc: { icms, ipi, pis, cofins } }
- extracted_error (string) — if processing fails
- _meta (optional) — free-form metadata and provenance

## Detailed step-by-step run (what happens on upload)
1. User uploads via frontend or posts to `/api/v1/documents/upload`.
2. Backend stores file to tmp dir and creates a DB entry with status `ingestao`.
3. Background worker calls `process_document`:
   a. Preprocessing: status `preprocessamento`, progress update saved.
   b. OCR: attempt text extraction from PDF via PyPDF2 or pdfminer; if none, use pdf2image + pytesseract (requires poppler and tesseract). Status `ocr`.
   c. Build prompt (ChatPromptTemplate) and call LLM(s) with a robust rotation/fallback strategy. Save `raw_extracted`.
   d. Parse raw_extracted into JSON (validate), fallback to `simple_receipt_parser` if LLM fails.
   e. Merge sources with `merge_extracted_sources` (LLM > fallback > specialist/ocr heuristics), then normalize via `normalize_extracted`.
   f. Save `extracted_data` and compute `aggregates` via `compute_aggregates`.
   g. Status transitions to `nlp`, `validacao`, `finalizado` with progress updates saved along the way.

## Reliability and auditability
- Atomic persistence: writes use the persistence module to avoid truncation and corruption.
- Provenance: `_meta` and `raw_extracted` are preserved for auditing LLM outputs.
- Report notes: `enrich_record` returns `report` describing fields filled and notes explaining replacements (LLM decisions, fallback usage).

## How the address extraction was improved
- The `specialist_agent._extract_address_parts` was made more defensive (valid UF list, CEP normalizer) and `refine_extracted` now:
  - Attempts to extract from any present `emitente.destino.endereco` fields.
  - If none present, scans for 'EMITENTE' or 'DESTINATARIO' blocks in the raw text.
  - As a final fallback, scans the full OCR/raw text for address-like lines (looking for CEP patterns, UF tokens, 'Bairro' labels) and maps them to parties that lack address parts.
- This increases recall for `bairro`, `municipio`, `uf`, and `cep` when the LLM or primary heuristics did not populate them.

## LLM-first policy for totals
- The system prefers LLM-parsed fields when the LLM is available and confident.
- When there is disagreement between LLM top-level `valor_total` and the sum of `itens`:
  - The system asks the LLM (via `llm_helper.verify_total_with_llm`) to decide: keep LLM top, use items-sum, or report uncertain.
  - If LLM is confident, its decision is followed; if uncertain or LLM unavailable, fallback to deterministic sum-of-items and we record why.

## Dashboard fix & recompute path
- If you observed zeros in the dashboard, after improving agents you'll likely need to refresh aggregates.
- Use the admin endpoint `/api/v1/admin/recompute_aggregates` to recompute all aggregates from current `extracted_data`.
- The frontend `Dashboard` prefers server-provided `aggregates.valor_total_calc` and will sum these values. If aggregates are missing or zero but items present, the recompute endpoint will refresh them.

## Operational checklist (how to run locally)
1. Install prerequisites (on Windows):
  - Python 3.10+ and pip
  - poppler (for pdf2image) and Tesseract OCR. For Windows, install the portable binaries and set `TESSERACT_CMD` env var to the tesseract.exe path or ensure it's in PATH.
2. Create virtual environment and install Python deps (from repository root):
```powershell
# from repo root
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
3. (Optional) set OpenRouter API key:
```powershell
$env:OPENROUTER_API_KEY = 'your_key_here'
```
4. Start backend (from backend folder):
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
5. Start frontend (from repo root):
```powershell
cd frontend
npm install
npm start
```
6. Upload sample file via UI and monitor the Dashboard and Results view.

## Troubleshooting
- If OCR fails: confirm `TESSERACT_CMD` and `poppler` paths are available. Check backend logs for explicit errors saved in `extracted_error`.
- If LLM calls return 401 or 429: ensure `OPENROUTER_API_KEY` is valid and monitor logs. The server rotates free models as fallback, but rate limits exist.
- If the dashboard shows zeros: run POST `/api/v1/admin/recompute_aggregates` to refresh aggregates; check individual document `/api/v1/documents/{id}/results` to inspect `extracted_data` and `aggregates`.

## Next improvements (proposals)
- Add unit tests and integration tests (pytest) for address parsing, items parsing, and aggregates. This will reduce regressions.
- Add a queued LLM verification step (async) to avoid blocking processing when calling secondary LLM checks.
- Add confidence/scoring into `extracted_data` (e.g., `valor_total.confidence`, `itens[].confidence`) to better control overrides.
- Improve UI to show provenance for every field (which agent/source filled it) to aid auditors.

---

If you want, I can now:
- run the recompute endpoint automatically and show the updated dashboard metrics, or
- add pytest tests and run them, or
- try a live E2E run (process `assets/nota_exemplo.pdf`) and post the before/after `extracted_data` + `aggregates` for inspection.

Which would you like me to do next?