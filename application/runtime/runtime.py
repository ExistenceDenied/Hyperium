from application.runtime.workflow.workflow_engine import WorkflowEngine
from core.agent_type import AgentType

class Runtime:

    def __init__(
        self,
        registry,
    ):

        self.registry = registry
        self.workflow = WorkflowEngine()

    def run(self, project):

        self.workflow.initialize(project)

        while True:

            work_item = self.workflow.next_work_item()
            if work_item is None:
                break

            agent = self.registry.get(work_item.assigned_agent)

            print()
            print("=" * 60)
            print(f"Executing: {work_item.title}")
            print(f"Agent: {agent.__class__.__name__}")

            result = agent.execute(project, work_item)

            print(f"Result type: {type(result)}")

            if result is None:
                raise ValueError(
                    f"{agent.__class__.__name__} returned None for work item '{work_item.title}'"
                )
            
            project.deliverables.extend(result.deliverables)

            # Voeg review toe voor elk niet-review work item
            if work_item.assigned_agent != AgentType.REVIEWER:

                review_item = self.workflow.create_review_work_item(work_item)

                project.work_items.append(review_item)
                self.workflow.add_work_items([review_item])

            # Voeg eventuele extra work items toe
            if result.new_work_items:
                project.work_items.extend(result.new_work_items)
                self.workflow.add_work_items(result.new_work_items)

            work_item.status = work_item.status.COMPLETED

        print()
        print("=" * 60)
        print("PROJECT COMPLETED")
        print(f"Deliverables: {len(project.deliverables)}")
        print(f"Work Items: {len(project.work_items)}")
