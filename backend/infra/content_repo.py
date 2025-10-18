import json
import os


class JSONContentRepository:
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_snippet(self, snippet_id: str) -> dict:
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(snippet_id, {"id": snippet_id, "text": "(content missing)"})

