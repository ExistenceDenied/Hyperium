from registry.agent_registry import AgentRegistry
from application.runtime.runtime import Runtime
from application.runtime.scheduler import Scheduler


class RuntimeBuilder:

    def build(self):

        scheduler = Scheduler()

        registry = AgentRegistry()

        return Runtime(scheduler=scheduler, registry=registry)
