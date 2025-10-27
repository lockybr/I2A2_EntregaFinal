# Descrição detalhada dos agentes

Este documento descreve cada agente presente em `backend/agents`, suas responsabilidades, entradas/saídas, pontos de falha comuns e sugestões de teste.

> Observação: os nomes de módulos podem variar levemente dependendo da refatoração local (por exemplo `backend.agents.ocr_agent` ou `agents.ocr_agent`). As funções descritas abaixo correspondem à implementação encontrada na árvore do repositório.

## Visão geral

O sistema organiza lógica especializada em "agentes" com responsabilidades claras:

- OCR (ocr_agent)
- NLP (nlp_agent)
- Specialist (specialist_agent)
- Enrichment (enrichment_agent)
- Validation (validation_agent)
- Retrieval / Reporting (retrieval_agent, reporting_agent)

Cada agente é um módulo Python que exporta funções reutilizáveis. O pipeline orquestra chamadas a esses agentes durante o processamento em background.

## ocr_agent.py

- Responsabilidade: extrair texto de documentos usando mecanismos apropriados para o tipo de arquivo.
- Entrada: caminho para arquivo (PDF, imagem, XML, CSV).
- Saída: uma string com o texto extraído (ocr_text) ou lançar erro quando incapaz.
- Técnicas: PyPDF2/pdfminer para texto selecionável; pdf2image + pytesseract para OCR de imagens; PIL para imagens simples.
- Variáveis ambient: `TESSERACT_CMD`, `POPPLER_PATH`.
- Falhas comuns: tesseract não instalado, poppler ausente no Windows, arquivos PDF criptografados.

Testes sugeridos:
- PDF com texto selecionável (assert: texto contém trechos conhecidos).
- PDF apenas imagem (assert: OCR retorna texto não vazio quando Tesseract disponível).
- Imagem JPG simples.

## nlp_agent.py

- Responsabilidade: aplicar regras de NLP, regex e prompt templates para transformar `ocr_text` em um objeto JSON bruto.
- Entrada: string `ocr_text`.
- Saída: JSON ou string (raw_extracted) que o processamento tentará parsear.
- Integração LLM: frequentemente usada em conjunto com `ChatOpenAI`/OpenRouter.
- Falhas comuns: LLM retorna texto com explicações (não apenas JSON), ou texto com artefatos que quebram o JSON.

Testes sugeridos:
- Texto de nota fiscal pequena -> ver se retorna JSON com `emitente` e `valor_total`.

## specialist_agent.py

- Responsabilidade: heurísticas especializadas para localizar seções de itens/produtos em documentos, extrair linhas de produto e normalizar descrições/quantidades/valores.
- Entrada: `ocr_text` (ou trechos dele).
- Saída: lista de itens estruturados.
- Falhas comuns: documentos com layout exótico ou colunas desalinhadas; separadores não padronizados.

Testes sugeridos:
- Cupom com várias linhas de produto em formatos comuns.

## enrichment_agent.py

- Responsabilidade: combinar saídas do LLM/heurísticas e aplicar regras adicionais para preencher campos faltantes, normalizar NCM/CST/CFOP quando detectável, e sugerir correções.
- Entrada: registro do documento (contendo `ocr_text`, `raw_extracted`, `extracted_data`).
- Saída: `extracted_data` atualizado e um dicionário `info` com `aggregates` e relatório de campos preenchidos.
- Falhas comuns: mudanças de versão no schema esperado pelo agente; dependências não injetadas.

Testes sugeridos:
- Documento com `raw_extracted` parcial -> execute `enrich_record` e verifique campos preenchidos.

## validation_agent.py

- Responsabilidade: validar formatos fiscais, como CNPJ, chaves de NF-e, datas e coerência numérica (ex.: soma de itens vs. valor total declarado).
- Entrada: `extracted_data` normalizado.
- Saída: relatórios de `passed`/`failed`, lista de erros e, opcionalmente, campos corrigidos.

Testes sugeridos:
- Caso com CNPJ inválido -> flag de erro.

## retrieval_agent.py e reporting_agent.py

- Responsabilidade: funções utilitárias para busca (fuzzy / por campos) e geração de relatórios agregados por período/emitente.

Testes sugeridos:
- Gerar relatório simples a partir do conjunto de documentos de teste.

## Orquestração entre agentes

- A orquestração é linear e acontece no `process_document` (em `backend/api/main.py`). O fluxo padrão é:
  1. OCR (ocr_agent)
  2. NLP + possível LLM (nlp_agent)
  3. Fallback heurístico (simple_receipt_parser) + specialist_agent quando disponível
  4. enrichment_agent (tenta mesclar e preencher)
  5. validation_agent

- Cada agente deve ser robusto: falhas em componentes opcionais (LLM) não devem parar o processamento. Erros são capturados e registrados no campo `extracted_error` do documento.

## Boas práticas para desenvolver agentes

- Assinar inputs e outputs com contratos simples (dicionários JSON padronizados).
- Escrever testes unitários para cada agente.
- Tratar entradas com dados ruins (None, strings vazias, valores numéricos com separadores locais).

---
Arquivo gerado automaticamente. Atualize conforme evoluem os agentes no código.
