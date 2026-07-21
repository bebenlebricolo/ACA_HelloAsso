from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class UserSettings:
    """User settings for the application"""
    selected_forms: List[str] = field(default_factory=list)
    extra_forms: Optional[str] = None
