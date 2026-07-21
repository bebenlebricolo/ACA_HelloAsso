from .OrderItem import OrderItem
from .Parseable import Parseable
from .Payer import Payer


from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OrderDetails(Parseable):
    """
    Detailed order information from /v5/orders/{id} endpoint
    """
    id: int = 0
    date: str = ""
    formSlug: str = ""
    formType: str = ""

    # Used to know if this order was payed with multiple payments or not.
    # When multiple payments is used, this field "name" will reflect it
    name: str = ""

    payer: Optional[Payer] = None
    items: List[OrderItem] = field(default_factory=list)
    # meta: Optional[Dict[str, str]] = None

    # organizationSlug: Optional[str] = None
    # organizationName: Optional[str] = None
    # organizationType: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an OrderDetails instance from raw API data"""

        self.id = raw_data.get("id", 0)
        self.date = raw_data.get("date", "")
        self.formSlug = raw_data.get("formSlug", "")
        self.formType = raw_data.get("formType", "")
        self.name = raw_data.get("name", "")

        payer_data = raw_data.get("payer")
        if payer_data:
            self.payer = Payer()
            self.payer.from_raw(payer_data)

        # Custom items parsing (that's the actually interesting part here.)
        items_data = raw_data.get("items", [])
        if items_data:
            self.items = []
            for item in items_data:
                if item is None:
                    continue
                current_item = OrderItem()
                current_item.from_raw(item)
                self.items.append(current_item)