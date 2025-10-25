# Sistema Inteligente de Extração de Dados Fiscais

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![React](https://img.shields.io/badge/react-18-blue.svg)

Sistema completo com **5 Agentes de IA** para extração automatizada de dados fiscais brasileiros.

## 🚀 Quick Start

```bash
# 1. Configure ambiente
cp .env.example .env
# Edite .env e adicione OPENAI_API_KEY

# 2. Inicie todos os serviços
docker-compose up -d

# 3. Acesse
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/api/docs
```

### Observações importantes

- O `Dockerfile` do `backend` instala o Tesseract dentro da imagem, portanto usar `docker-compose` é a forma recomendada para evitar instalar Tesseract localmente.
- Para desenvolvimento local sem Docker (Windows), você pode colocar um binário portátil do Tesseract em `backend/tools/tesseract/tesseract.exe`. O backend detecta automaticamente esse executável ou a variável de ambiente `TESSERACT_CMD`.

### Execução local (sem Docker)

1. Backend (Windows/macOS/Linux)

```powershell
# Windows PowerShell (exemplo)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# se você tem tesseract instalado globalmente, tudo pronto
# caso contrário, defina a variável TESSERACT_CMD para apontar para o binário
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Frontend

```powershell
cd frontend
npm install
npm start
```

### CI / GitHub Actions

Há um workflow de exemplo em `.github/workflows/ci.yml` que compila e testa a aplicação em cada push. Para publicar imagens em um registry, adicione as credenciais como secrets no repositório.

### Makefile & helper scripts

- Execute `make build` para construir imagens via Docker Compose.
- Execute `make up` para subir os serviços (docker compose up -d).
- `make renormalize` executa `backend/re_normalize_db.py` para recalcular e persistir agregados (valor_total_calc e impostos_calc) em `backend/api/documents_db.json`.
- Há scripts em `scripts/` para baixar um Tesseract portátil:
	- `scripts/get_tesseract.sh` (Linux/macOS)
	- `scripts/get_tesseract.ps1` (Windows PowerShell)

### Publishing images (GHCR)

Use the provided workflow `.github/workflows/publish.yml` which will build images and push to GHCR when `GHCR_TOKEN` is configured in repository Secrets. The workflow builds multi-arch images for backend/frontend and runs a smoke `docker compose build`.

---

Se quiser, eu posso preparar um script `make` e um workflow de publicação pronto para sua conta do GitHub Packages/Registry — me diga se prefere que eu o adicione e eu preparo o arquivo com placeholders para secrets.

## 📦 Componentes

### Backend (Python/FastAPI)
- **5 Agentes Especializados**: Recuperação, OCR, NLP, Validação, Relatórios
- **CrewAI**: Orquestração de agentes
- **Tesseract OCR**: Extração de texto (português BR)
- **spaCy NLP**: Named Entity Recognition
- **PostgreSQL + MongoDB + Redis**

### Frontend (React/TypeScript)
- **Dashboard**: Monitoramento em tempo real
- **Upload**: Drag-and-drop de documentos
- **Pipeline View**: Status das 6 etapas
- **Results**: Visualização de dados extraídos
- **Export**: JSON, XML, CSV

## 🏗️ Arquitetura

Pipeline de 6 etapas:
1. Ingestão → 2. Pré-processamento → 3. OCR → 4. NLP → 5. Validação → 6. Exportação

## 📚 Tecnologias

- **Backend**: Python 3.11, FastAPI, CrewAI, Tesseract, spaCy
- **Frontend**: React 18, TypeScript, Axios
- **Banco**: PostgreSQL 16, MongoDB 7, Redis 7
- **Infra**: Docker, Kubernetes, Nginx

## 📄 Licença

MIT License
