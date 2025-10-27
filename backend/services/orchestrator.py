"""Orquestrador CrewAI - Coordena os 5 agentes"""
from crewai import Crew, Process
from langchain_openai import ChatOpenAI
from agents import *
import os
import sys
from pydantic import SecretStr


class FiscalCrewOrchestrator:
    """Orquestrador principal usando CrewAI"""

    def __init__(self):
        # Read OpenRouter API key from environment for orchestrator usage as well
        _raw_key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_KEY')
        OPENROUTER_API_KEY = SecretStr(_raw_key) if _raw_key else None
        OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', "gpt-4")
        if not OPENROUTER_API_KEY:
            print('[CONFIG] Warning: OPENROUTER_API_KEY not set for orchestrator. LLM calls may fail.', file=sys.stderr)
        self.llm = ChatOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1", model=OPENROUTER_MODEL, temperature=0.1)

        # Inicializar 5 agentes
        self.retrieval = DocumentRetrievalAgent(self.llm)
        self.ocr = OCRProcessingAgent(self.llm)
        self.nlp = NLPExtractionAgent(self.llm)
        self.validation = ValidationAgent(self.llm)
        self.reporting = ReportingAgent(self.llm)

    def process_document(self, document_id):
        """Processa documento através do pipeline de 6 etapas"""

        # Criar crew com todos os agentes
        crew = Crew(
            agents=[
                self.retrieval.agent,
                self.ocr.agent,
                self.nlp.agent,
                self.validation.agent,
                self.reporting.agent
            ],
            process=Process.sequential,
            verbose=2
        )

        # Executar pipeline
        result = crew.kickoff()

        return {
            "document_id": document_id,
            "status": "completed",
            "result": result
        }
