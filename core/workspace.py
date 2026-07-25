from pathlib import Path


class Workspace:

    def __init__(self, root: Path):

        self.root = root
        self.root.mkdir(exist_ok=True)

    def write(self, filename: str, content: str):

        file = self.root / filename

        file.write_text(content, encoding="utf-8")

    def read(self, filename: str):

        file = self.root / filename

        return file.read_text(encoding="utf-8")

    def exists(self, filename: str):

        return (self.root / filename).exists()
