from dataclasses import dataclass

from core.entities.project import Project
from core.workspace import Workspace


@dataclass
class RuntimeContext:

    project: Project

    workspace: Workspace
