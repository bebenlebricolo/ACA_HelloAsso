from .CustomField import CustomField
from .OrderState import OrderState
from .Parseable import Parseable


from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OrderItem(Parseable):
    """
    Partial mapping of an item from a HelloAsso order/form, used in aggregated payment data
    """
    id: int = 0
    name: str = ""
    tier_id: int = 0
    amount: int = 0
    initial_amount: int = 0
    state: OrderState = OrderState.Unknown
    type: str = ""
    tier_description: str = ""

    custom_fields: List[CustomField] = field(default_factory=list)

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an OrderItem instance from raw API data"""
        self.id = raw_data.get("id", 0)
        self.name = raw_data.get("name", "")
        self.tier_id = raw_data.get("tierId", 0)
        self.amount = raw_data.get("amount", 0)
        self.initial_amount = raw_data.get("initialAmount", 0)

        if raw_data.get("state"):
            self.state = OrderState[raw_data.get("state", OrderState.Unknown.value)]

        self.type = raw_data.get("type", "")
        self.tier_description = raw_data.get("tierDescription", "")

        # Custom fields are where the interesting additional metadata is added.
        custom_fields_data = raw_data.get("customFields", [])
        if custom_fields_data:
            self.custom_fields = []
            for field in custom_fields_data:
                if field is None:
                    continue
                current_field = CustomField()
                current_field.from_raw(field)
                self.custom_fields.append(current_field)