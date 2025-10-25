"""Agente de Relatórios"""
from crewai import Agent, Task

class ReportingAgent:
    def __init__(self, llm):
        self.llm = llm
        self.agent = self._create_agent()

    def _create_agent(self):
        return Agent(
            role="Reporting and Integration Specialist",
            goal="Generate reports and integrate with external systems",
            backstory="Expert in data export (JSON, XML, CSV) and ERP integration",
            llm=self.llm,
            verbose=True
        )

    def create_task(self, data):
        return Task(
            description=f"Generate reports and export data",
            agent=self.agent,
            expected_output="Exported files and integration status"
        )
