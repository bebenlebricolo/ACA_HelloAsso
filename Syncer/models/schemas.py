"""
Data schemas for HelloAsso Syncer

This module contains all dataclasses used to represent:
- Authentication configuration
- Payment data from HelloAsso API
- Order details from /orders endpoint
- Aggregated payment data (payment + order details joined)

Based on real API responses from HelloAsso v5 API.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# =============================================================================
# Sub-models (nested objects)
# =============================================================================

class Parseable:
    """Base class for models that can be created from raw API data"""

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an instance from raw API data"""
        raise NotImplementedError(
            "from_raw method must be implemented in subclasses")


@dataclass
class Payer(Parseable):
    """Payer information from HelloAsso"""
    email: str = ""
    country: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zipcode: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create a Payer instance from raw API data"""
        self.email = raw_data.get("email", "")
        self.country = raw_data.get("country", "")
        self.firstName = raw_data.get("firstName", "")
        self.lastName = raw_data.get("lastName", "")
        self.address = raw_data.get("address", "")
        self.city = raw_data.get("city", "")
        self.zipcode = raw_data.get("zipcode", "")


@dataclass
class Item(Parseable):
    """An item from a HelloAsso order/form"""
    id: Optional[int] = None
    type: Optional[str] = None
    amount: Optional[int] = None
    shareAmount: Optional[int] = None
    shareItemAmount: Optional[int] = None
    state: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an Item instance from raw API data"""

        self.id = raw_data.get("id")
        self.type = raw_data.get("type")
        self.amount = raw_data.get("amount")
        self.shareAmount = raw_data.get("shareAmount")
        self.shareItemAmount = raw_data.get("shareItemAmount")
        self.state = raw_data.get("state")


@dataclass
class Order(Parseable):
    """Order information embedded in payment data"""
    id: int = 0
    date: Optional[str] = None
    formSlug: Optional[str] = None
    formType: Optional[str] = None
    formName: Optional[str] = None
    organizationName: Optional[str] = None
    organizationSlug: Optional[str] = None
    organizationType: Optional[str] = None
    organizationIsUnderColucheLaw: Optional[bool] = None
    meta: Optional[Dict[str, str]] = None
    isAnonymous: Optional[bool] = None
    isAmountHidden: Optional[bool] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create an Order instance from raw API data"""
        self.id = raw_data["id"]
        self.date = raw_data["date"]
        self.formSlug = raw_data["formSlug"]
        self.formType = raw_data["formType"]
        self.formName = raw_data["formName"]
        self.organizationName = raw_data["organizationName"]
        self.organizationSlug = raw_data["organizationSlug"]
        self.organizationType = raw_data["organizationType"]
        self.organizationIsUnderColucheLaw = raw_data["organizationIsUnderColucheLaw"]
        self.meta = raw_data["meta"]
        self.isAnonymous = raw_data["isAnonymous"]
        self.isAmountHidden = raw_data["isAmountHidden"]


# =============================================================================
# Main Models
# =============================================================================

@dataclass
class AuthConfig:
    """Authentication configuration for HelloAsso API"""
    client_id: str
    client_secret: str


@dataclass
class RawPayment(Parseable):
    """
    Raw payment data as returned by /v5/organizations/{org}/forms/{type}/{slug}/payments

    Note: Amounts are in cents (e.g., 9000 = 90.00 €)
    """
    id: int = 0
    date: str = ""
    amount: int = 0
    state: str = ""
    paymentMeans: Optional[str] = None
    installmentNumber: Optional[int] = None
    cashOutDate: Optional[str] = None
    idCashOut: Optional[int] = None
    cashOutState: Optional[str] = None
    paymentReceiptUrl: Optional[str] = None

    order: Order = field(default_factory=Order)
    payer: Payer = field(default_factory=Payer)
    items: List[Item] = field(default_factory=list)
    meta: Optional[Dict[str, str]] = None
    refundOperations: List[Dict[str, Any]] = field(default_factory=list)

    formSlug: Optional[str] = None
    formType: Optional[str] = None

    def from_raw(self, raw_data: Dict[str, Any]) -> None:
        """Create a RawPayment instance from raw API data"""

        self.id = raw_data.get("id", 0)
        self.date = raw_data.get("date", "")
        self.amount = raw_data.get("amount", 0)
        self.state = raw_data.get("state", "")
        self.paymentMeans = raw_data["paymentMeans"]
        self.installmentNumber = raw_data["installmentNumber"]
        self.cashOutDate = raw_data["cashOutDate"]
        self.idCashOut = raw_data["idCashOut"]
        self.cashOutState = raw_data["cashOutState"]
        self.paymentReceiptUrl = raw_data["paymentReceiptUrl"]

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
                current_item = Item()
                current_item.from_raw(item)
                self.items.append(current_item)


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
    state: str = ""
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
        self.state = raw_data.get("state", "")
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



@dataclass
class OrderDetails(Parseable):
    """
    Detailed order information from /v5/orders/{id} endpoint
    """
    id: int = 0
    date: str = ""
    formSlug: str = ""
    formType: str = ""

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


@dataclass
class AggregatedPayment:
    """
    Aggregated payment data combining RawPayment and OrderDetails.
    All amounts are converted to euros (float) for easier reading.
    """
    payment_id: int
    payment_date: str
    payment_amount: float
    form_slug: str

    # Member data (partial)
    first_name: str
    last_name: str
    email: str

    payment_receipt_url: Optional[str] = None
    custom_fields: List[CustomField] = field(default_factory=list)

