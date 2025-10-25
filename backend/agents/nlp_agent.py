"""Agente de Extração NLP"""
from crewai import Agent, Task

class NLPExtractionAgent:
    def __init__(self, llm):
        self.llm = llm
        self.agent = self._create_agent()

    def _create_agent(self):
        # Detailed instructions: the agent must parse the provided OCR text and produce
        # a compact, normalized JSON following the schema in prompt.md. Prioritize
        # fields that populate the UI tabs: Dados da Nota, Emitente, Destinatário,
        # Itens, Tributos, Totais, Outros. When uncertain, return null for the field
        # and include a short "confidence" or "extracted_from" note where possible.
        return Agent(
            role="NLP Extraction Specialist",
            goal=("Extract and normalize fiscal information from OCR/text for NF-e, cupons and similar "
                  "documents. Output a concise JSON matching the schema: emitente, destinatario, itens, "
                  "impostos, codigos_fiscais, numero_nota, chave_acesso, data_emissao, natureza_operacao, "
                  "forma_pagamento, valor_total. Favor usar chaves estáveis e legíveis."),
            backstory=("You are an expert in Brazilian fiscal documents and tax codes (CFOP, CST, NCM, CNPJ). "
                       "Adapt to different layouts and extract the most relevant values for display in a web UI."),
            llm=self.llm,
            verbose=True
        )

    def create_task(self, text):
        instruction = (
            "Given the OCR/text of a fiscal document, extract the following fields and return VALID JSON only. "
            "Structure the output as an object with keys: emitente, destinatario, itens (array), impostos, codigos_fiscais, "
            "numero_nota, chave_acesso, data_emissao, natureza_operacao, forma_pagamento, valor_total, outros. "
            "Each item in itens must have: descricao, quantidade, unidade, valor_unitario, valor_total, codigo (optional), ncm, cfop, cst/csosn. "
            "If a value cannot be confidently extracted, set it to null rather than guessing. Include small notes in a top-level "
            "'_meta' object if you want to record confidence or extraction hints. Use dot notation keys only in _meta; main keys must match schema."
        )
        return Task(
            description=instruction,
            agent=self.agent,
            expected_output="JSON object following the fiscal extraction schema (emitente, destinatario, itens, impostos, codigos_fiscais, numero_nota, chave_acesso, data_emissao, natureza_operacao, forma_pagamento, valor_total, outros)"
        )
