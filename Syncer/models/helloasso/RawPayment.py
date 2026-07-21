from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .Order import Order
from .Parseable import Parseable
from .Payer import Payer
from .PaymentItem import PaymentItem
from .PaymentState import PaymentState

@dataclass
class RawPayment(Parseable):
    """
    Raw payment data as returned by /v5/organizations/{org}/forms/{type}/{slug}/payments

    Note: Amounts are in cents (e.g., 9000 = 90.00 €)
    """
    id: int = 0
    date: str = ""
    amount: int = 0
    state: PaymentState = PaymentState.Unknown
    paymentMeans: Optional[str] = None
    installmentNumber: Optional[int] = None
    cashOutDate: Optional[str] = None
    idCashOut: Optional[int] = None
    cashOutState: Optional[str] = None
    paymentReceiptUrl: Optional[str] = None

    order: Order = field(default_factory=Order)
    payer: Payer = field(default_factory=Payer)
    items: List[PaymentItem] = field(default_factory=list)
    meta: Optional[Dict[str, str]] = None
    refundOperations: List[Dict[str, Any]] = field(default_factory=list)

    formSlug: Optional[str] = None
    formType: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create a RawPayment instance from raw API data"""

        self.id = raw_data.get("id", 0)
        self.date = raw_data.get("date", "")
        self.amount = raw_data.get("amount", 0)

        if(raw_data.get("state")):
            self.state = PaymentState[raw_data.get("state", PaymentState.Unknown.value)]

        self.paymentMeans = raw_data["paymentMeans"]
        self.installmentNumber = raw_data["installmentNumber"]

        self.cashOutState = raw_data.get("cashOutState", None) # When refused, none of the cashoutDate/idCashOut or paymentReceiptUrl are present, so we need to handle this case gracefully.
        self.cashOutDate = raw_data.get("cashOutDate",None)
        self.idCashOut = raw_data.get("idCashOut",None)
        self.paymentReceiptUrl = raw_data.get("paymentReceiptUrl", None)

        order_data = raw_data["order"]
        if order_data:
            self.order = Order()
            self.order.from_raw(order_data)

        payer_data = raw_data["payer"]
        if payer_data:
            self.payer = Payer()
            self.payer.from_raw(payer_data)

        items_data = raw_data.get("items", [])
        if items_data:
            self.items = []
            for item in items_data:
                if item is None:
                    continue
                current_item = PaymentItem()
                current_item.from_raw(item)
                self.items.append(current_item)