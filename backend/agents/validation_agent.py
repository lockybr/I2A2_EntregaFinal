"""Agente de Validação"""
from crewai import Agent, Task

class ValidationAgent:
    def __init__(self, llm):
        self.llm = llm
        self.agent = self._create_agent()

    def _create_agent(self):
        # Validation agent should normalize and validate extracted fields, producing
        # a short validation report and suggestions to correct obvious OCR/NLP mistakes.
        return Agent(
            role="Data Validation Expert",
            goal=("Validate and normalize extracted fiscal data: verify formats for CNPJ/CPF, dates, monetary values, "
                  "and common fiscal codes (CFOP, NCM, CST). Produce a compact validation report and normalized output."),
            backstory="Specialist in Brazilian tax rules and data normalization",
            llm=self.llm,
            verbose=True
        )

    def create_task(self, data):
        instruction = (
            "Receive the extracted JSON and perform normalization and validation. Return an object with keys: "
            "normalized (the normalized extraction ready for UI), issues (array of detected problems), "
            "and confidence (0-1). Normalize CNPJ (only digits), dates (ISO format YYYY-MM-DD), and monetary values (float)."
        )
        return Task(
            description=instruction,
            agent=self.agent,
            expected_output="JSON with keys: normalized, issues, confidence"
        )
