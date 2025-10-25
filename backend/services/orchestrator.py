"""Orquestrador CrewAI - Coordena os 5 agentes"""
from crewai import Crew, Process
from langchain_openai import ChatOpenAI
from agents import *

class FiscalCrewOrchestrator:
    """Orquestrador principal usando CrewAI"""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.1)

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
