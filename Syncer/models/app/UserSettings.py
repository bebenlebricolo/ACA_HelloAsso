from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
import json

from ..Jsonable import Jsonable
@dataclass
class UserSettings(Jsonable):
    """User settings for the application"""
    selected_forms: List[str] = field(default_factory=list)
    extra_forms: Optional[str] = None

    def from_json(self, content: dict[str, Any]) -> None:
        self.selected_forms = content.get("selected_forms", [])
        self.extra_forms = content.get("extra_forms", None)

    def to_json(self) -> dict[str, Any]:
        return {
            "selected_forms" : self.selected_forms,
            "extra_forms" : self.extra_forms
        }

    def load_from_file(self, filepath: Path):
        with open(filepath, "r") as file:
            content = json.load(file)
        self.from_json(content)

    def save_to_file(self, filepath: Path):
        with open(filepath, 'w') as file:
            json.dump(self.to_json(), file)
