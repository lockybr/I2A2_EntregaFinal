"""Agente de Recuperação de Documentos"""
from crewai import Agent, Task

class DocumentRetrievalAgent:
    def __init__(self, llm):
        self.llm = llm
        self.agent = self._create_agent()

    def _create_agent(self):
        return Agent(
            role="Document Retrieval Specialist",
            goal="Fetch and validate fiscal documents from multiple sources",
            backstory="Expert in Brazilian fiscal systems (SEFAZ, ERPs, email)",
            llm=self.llm,
            verbose=True
        )

    def create_task(self, sources):
        return Task(
            description=f"Retrieve documents from: {sources}",
            agent=self.agent,
            expected_output="List of downloaded documents with metadata"
        )
