from dataclasses import dataclass
from typing import Any, Dict, Optional

from .OrderState import OrderState
from .Parseable import Parseable

@dataclass
class PaymentItem(Parseable):
    """An item from a HelloAsso order/form"""
    id: Optional[int] = None
    type: Optional[str] = None
    amount: Optional[int] = None
    shareAmount: Optional[int] = None
    shareItemAmount: Optional[int] = None
    state: Optional[OrderState] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an Item instance from raw API data"""

        self.id = raw_data.get("id")
        self.type = raw_data.get("type")
        self.amount = raw_data.get("amount")
        self.shareAmount = raw_data.get("shareAmount")
        self.shareItemAmount = raw_data.get("shareItemAmount")

        if raw_data.get("state"):
            self.state = OrderState[raw_data.get("state", OrderState.Unknown.value)]