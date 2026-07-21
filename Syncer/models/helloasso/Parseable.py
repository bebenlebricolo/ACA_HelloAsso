# =============================================================================
# Sub-models (nested objects)
# =============================================================================

from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Parseable:
    """Base class for models that can be created from raw API data"""

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an instance from raw API data"""
        raise NotImplementedError(
            "from_raw method must be implemented in subclasses")