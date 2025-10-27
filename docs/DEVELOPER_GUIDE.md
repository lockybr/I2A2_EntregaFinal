# Guia do Desenvolvedor

Este documento é um guia prático para desenvolvedores que irão trabalhar localmente no projeto. Contém instruções de setup, execução, debugging, testes, e procedimentos operacionais comuns (limpeza do DB, reprocessamento, backup).

## Estrutura do repositório (resumida)

- backend/: código do servidor (FastAPI) e agentes
  - backend/api/: implementação da API, `main.py`, `persistence.py`
  - backend/agents/: agentes especializados (ocr_agent, nlp_agent, enrichment_agent, validation_agent, retrieval_agent, reporting_agent)
- frontend/: UI em React (Create React App)
- poppler/: binários de poppler incluídos localmente (opcional)
- docs/: documentação (ARCHITECTURE.md, AGENTS.md, DEVELOPER_GUIDE.md)

## Requisitos

- Python 3.10+ (3.11 recomendado)
- Node.js 16+ / npm
- Tesseract OCR (opcional se trabalhar com PDFs imagem)
- git

Recomenda-se usar um ambiente virtual para o backend e gerenciadores de versão para Node.

## Variáveis de ambiente relevantes

- `OPENROUTER_API_KEY` — chave para integração com OpenRouter / LLM (opcional).
- `DOCUMENTS_DB_PATH` — caminho alternativo para o arquivo JSON de persistência (útil para apontar para `documents_db.clean.json`).
- `TESSERACT_CMD` — caminho absoluto para o executável do Tesseract.
- `POPPLER_PATH` — caminho para a pasta contendo os binários do poppler (windows).

## Executando em desenvolvimento (PowerShell)

Backend (crie e ative virtualenv, instale dependências):

```powershell
cd C:\labz\fiscal-extraction-system-COMPLETO\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Opcional: exponha um DB limpo para evitar carregar arquivos corrompidos
$env:DOCUMENTS_DB_PATH = "C:\labz\fiscal-extraction-system-COMPLETO\backend\api\documents_db.clean.json"
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd C:\labz\fiscal-extraction-system-COMPLETO\frontend
npm install
npm start
```

Docker Compose (alternativa):

```powershell
cd C:\labz\fiscal-extraction-system-COMPLETO
docker-compose up --build
```

## Trabalhando com o DB JSON

O backend persiste dados em `backend/api/documents_db.json` por padrão. Para recuperação segura e testes:

- Não exclua arquivos em `backend/api/archives/` — eles são backups importantes.
- Se precisar começar do zero, crie um arquivo vazio `documents_db.clean.json` com `{}` e inicie o backend apontando `DOCUMENTS_DB_PATH` para ele (exemplo acima).
- Endpoints administrativos:
  - `POST /api/v1/admin/clear_db` — backup + limpa o DB atual.
  - `POST /api/v1/admin/reload_db` — recarrega o DB do disco para memória.
  - `GET /api/v1/admin/db_info` — mostra o caminho e prévia do DB que o processo usa.

Exemplo: limpar DB via curl (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/admin/clear_db
```

## Reprocessamento de documentos

Se você alterou a lógica de extração ou quer reprocessar documentos historicizados:

1. Use `POST /api/v1/documents/{id}/enrich` para reexecutar heurísticas de enriquecimento em um documento específico.
2. Para reprocessar em massa, escreva um pequeno script Python que leia `documents_db.json`, itere pelos ids e chame o endpoint `/api/v1/documents/{id}/enrich` ou acione diretamente funções do agente (execução offline).

Exemplo básico (PowerShell) usando o endpoint enrich:

```powershell
#$docs = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/v1/documents
foreach ($d in $docs.documents) { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/documents/$($d.id)/enrich" }
```

Aviso: reprocessamentos em massa podem sobrecarregar a API e a máquina local; prefira executar em lotes.

## Debugging e logs

- O servidor imprime logs consolidados no stderr com prefixos como `[PROCESSAMENTO]`, `[LLM]`, `[PERSIST]`. Use essas tags para filtrar.
- Caso o arquivo JSON esteja sendo movido para `.corrupt_*`, inspecione `backend/api/archives/` para localizar o backup e avaliar o que deu errado.

## Testes

- Há scripts de teste em `backend/` (ex.: `test_upload.py`, `test_llm.py`). Execute-os após configurar o ambiente.
- Recomendamos criar testes unitários para cada agente em `backend/agents/` usando pytest.

## Como contribuir (pra um dev local)

1. Crie uma branch com nome descritivo: `feature/<curta-descricao>` ou `fix/<curta-descricao>`.
2. Faça commits pequenos e focalizados, escrevendo mensagens claras.
3. Atualize `docs/ARCHITECTURE.md` se a arquitetura mudar.
4. Abra PR apontando para `main` e descreva o que foi alterado, incluindo comandos para reproduzir.

## Procedimento de commit (exemplo)

```powershell
cd C:\labz\fiscal-extraction-system-COMPLETO
git checkout -b docs/update-architecture
git add docs/ARCHITECTURE.md docs/AGENTS.md docs/DEVELOPER_GUIDE.md README.md
git commit -m "docs: documentação detalhada da arquitetura, agentes e guia do desenvolvedor"
git push --set-upstream origin docs/update-architecture
```

## Restaurando dados de backup

1. Pare o serviço que usa o `documents_db.json`.
2. Copie o backup desejado de `backend/api/archives/` para `backend/api/documents_db.json`.
3. Inicie o serviço e chame `POST /api/v1/admin/reload_db`.

## Observações finais

Esta documentação é um ponto de partida. Para mudanças maiores (migração de DB, alta disponibilidade) recomendamos planejar migrações, testes de carga e preparar um ambiente com banco de dados robusto (Postgres, MongoDB, etc.).

---
Arquivo gerado / atualizado para facilitar onboarding de desenvolvedores.

# Developer Guide — Fiscal Extraction System

This guide helps contributors start a development environment, run the backend and frontend locally on Windows, run a sample end-to-end processing, and run basic tests.

## Prerequisites

- Windows 10/11
- Python 3.10+ (3.11 recommended)
- Node.js 16+ and npm
- Git
- poppler (for pdf2image) and Tesseract OCR
  - You can download portable builds and set `TESSERACT_CMD` accordingly.

## Recommended environment variables

Set these in PowerShell for a dev session:

```powershell
# Optional: OpenRouter key for LLM
$env:OPENROUTER_API_KEY = 'your_openrouter_key'

# If using a portable tesseract, point to the exe
$env:TESSERACT_CMD = 'C:\tools\tesseract\tesseract.exe'

# Optional: storage dir override (use a repo-relative path or absolute)
# Example (repo-root relative):
$env:BACKEND_STORAGE_DIR = (Join-Path (Resolve-Path .).Path 'backend\storage')
```

## Start backend locally (PowerShell)

```powershell
# From the repository root, run:
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Run server (module path is api.main when run from the backend folder)
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Notes:
- If you run `uvicorn` from the repo root, use `uvicorn backend.api.main:app --reload --port 8000` and ensure `backend` is a package importable from Python (the project root should be on PYTHONPATH).

## Start frontend (PowerShell)

```powershell
# From the repository root, run:
cd frontend
npm install
npm start
```

Open http://localhost:3000 and the backend API at http://localhost:8000.

## Run an end-to-end sample (via API)

You can upload a sample file (`assets/nota_exemplo.pdf`) using PowerShell and `Invoke-RestMethod`.

```powershell
# from repo root, use relative path to the sample asset
$files = @{ file = Get-Item (Join-Path (Resolve-Path .).Path 'assets\nota_exemplo.pdf') }
$response = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/documents/upload -Method Post -Form $files
$response | ConvertTo-Json -Depth 6
```

After upload, poll the listing endpoint:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/documents -Method GET | ConvertTo-Json -Depth 6
```

Or inspect a specific document (replace {id}):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/documents/{id}/results -Method GET | ConvertTo-Json -Depth 6
```

## Admin workflows

- Reload DB after manual edit or restore:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/reload_db -Method POST | ConvertTo-Json -Depth 6
```

- Recompute aggregates for all records:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/admin/recompute_aggregates -Method POST | ConvertTo-Json -Depth 6
```

## Tests (suggested)

- Add pytest tests under `backend/tests/`.
- Suggested quick tests:
  - `tests/test_specialist_agent.py` — verify `specialist_agent._extract_items_from_lines` handles multi-line items.
  - `tests/test_enrichment_agent.py` — feed synthetic OCR text and ensure `compute_aggregates` produces expected totals.

Run tests with:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
pytest -q
```

## Code style and linting

- Python: black, flake8 (not required but recommended). To run black:

```powershell
python -m pip install black
python -m black backend
```

- Frontend: use `npm run lint` if configured, or `npx eslint src`.

## Cleaning up unused files

Be conservative when removing files. If you want me to prepare an automated detection of unused JS/CSS files and propose a safe deletion patch (with PR) I can do that. I can also move deprecated files to a `deprecated/` folder if you prefer a non-destructive approach.

### Sanitizing persisted DB before committing

The repository contains `backend/api/documents_db.json` which may include developer-local absolute paths (e.g., tmp file paths). Before pushing the repo, run the provided sanitizer to avoid leaking local paths:

```powershell
# from repo root
python scripts/sanitize_documents_db.py
```

This will create a sanitized copy and optionally replace the original with a backup created. Inspect the sanitized file before committing.

## Contact / Next steps I can automate for you

I can:
- Run the recompute aggregates endpoint and report results.
- Generate unit tests for the address and item parsing heuristics and run them.
- Create a small CI workflow that runs tests on each PR.

Choose one and I'll proceed to implement it.
