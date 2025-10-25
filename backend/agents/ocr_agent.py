"""Agente de Processamento OCR"""
from crewai import Agent, Task

class OCRProcessingAgent:
    def __init__(self, llm):
        self.llm = llm
        self.agent = self._create_agent()

    def _create_agent(self):
        # This agent should focus on producing high-quality OCR text and metadata.
        # Provide plain text suitable for downstream NLP agents and include simple
        # location hints or page/line markers when useful. Return confidence hints
        # when possible.
        return Agent(
            role="OCR Processing Expert",
            goal=("Produce the cleanest possible OCR output from the document and return "
                  "plain text with optional structured metadata (page, line ranges, confidence). "
                  "Try to preserve line breaks and sections that indicate headers, totals, and table rows."),
            backstory="Specialist in OCR and preprocessing for Portuguese fiscal documents (Tesseract, image cleanup)",
            llm=self.llm,
            verbose=True
        )

    def create_task(self, document_path):
        instruction = (
            "Run OCR and return a JSON object with keys: text (plain OCR string), pages (optional array of page texts), "
            "and optional confidences. Try to separate obvious sections (header, items table, totals, footer) using newlines. "
            "Clean common OCR artifacts but avoid removing numeric sequences that may be invoice/chave/cnpj."
        )
        return Task(
            description=instruction + f" Document path: {document_path}",
            agent=self.agent,
            expected_output="JSON with keys: text, pages (optional), confidences (optional)"
        )
