from infrastructure.llm.ollama_provider import OllamaProvider

from application.project.project_builder import ProjectBuilder
from application.project.project_service import ProjectService
from core.missions.mission import Mission
from core.resources.ai_resource import AIResource


def main() -> None:
    mission = Mission(
        title="Create a Business Analysis training",
        objective="Develop a complete one-day Business Analysis training for junior consultants.",
    )

    llm = OllamaProvider()

    analysis_service, planning_service, execution_engine = (
        ProjectBuilder.build(llm)
    )

    project_service = ProjectService(
        analysis_service,
        planning_service,
        execution_engine,
    )

    claude = AIResource(
        name="Claude",
        provider="Anthropic",
        model="claude-opus-4",
    )

    project = project_service.execute(
        mission,
        resources=[claude],
    )

    print(project.execution_result)


if __name__ == "__main__":
    main()