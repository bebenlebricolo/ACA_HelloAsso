from .Parseable import Parseable


from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CustomField(Parseable):
    """
    Custom field data from HelloAsso order/form
    """
    id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    answer: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create a CustomField instance from raw API data"""
        self.id = raw_data.get("id", None)
        self.name = raw_data.get("name", None)
        self.type = raw_data.get("type", None)
        self.answer = raw_data.get("answer", None)

        if self.id == 6229897:
            pass