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

@dataclass
class Payer:
    """Payer information from HelloAsso"""
    email: str
    country: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zipcode: Optional[str] = None


@dataclass
class Item:
    """An item from a HelloAsso order/form"""
    id: Optional[int] = None
    type: Optional[str] = None
    amount: Optional[int] = None
    shareAmount: Optional[int] = None
    shareItemAmount: Optional[int] = None
    state: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class Order:
    """Order information embedded in payment data"""
    id: Optional[int] = None
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


# =============================================================================
# Main Models
# =============================================================================

@dataclass
class AuthConfig:
    """Authentication configuration for HelloAsso API"""
    client_id: str
    client_secret: str


@dataclass
class RawPayment:
    """
    Raw payment data as returned by /v5/organizations/{org}/forms/{type}/{slug}/payments
    
    Note: Amounts are in cents (e.g., 9000 = 90.00 €)
    """
    id: int
    date: str
    amount: int
    state: str
    paymentMeans: Optional[str] = None
    installmentNumber: Optional[int] = None
    cashOutDate: Optional[str] = None
    idCashOut: Optional[int] = None
    cashOutState: Optional[str] = None
    paymentReceiptUrl: Optional[str] = None
    
    order: Optional[Order] = None
    payer: Optional[Payer] = None
    items: List[Item] = field(default_factory=list)
    meta: Optional[Dict[str, str]] = None
    refundOperations: List[Dict[str, Any]] = field(default_factory=list)
    
    formSlug: Optional[str] = None
    formType: Optional[str] = None


@dataclass
class OrderDetails:
    """
    Detailed order information from /v5/orders/{id} endpoint
    """
    id: int
    date: str
    formSlug: str
    formType: str
    amount: int
    state: str
    
    totalAmount: Optional[int] = None
    feeAmount: Optional[int] = None
    formName: Optional[str] = None
    
    payer: Optional[Payer] = None
    items: List[Item] = field(default_factory=list)
    customFields: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, str]] = None
    
    organizationSlug: Optional[str] = None
    organizationName: Optional[str] = None
    
    paymentDate: Optional[str] = None
    paymentMeans: Optional[str] = None
    paymentState: Optional[str] = None
    paymentAmount: Optional[int] = None
    
    emergency_contact: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedPayment:
    """
    Aggregated payment data combining RawPayment and OrderDetails.
    All amounts are converted to euros (float) for easier reading.
    """
    payment_id: int
    order_id: int
    payment_date: str
    payment_amount: float
    payment_state: str
    first_name: str
    last_name: str
    email: str
    form_slug: str
    form_type: str
    
    order_date: Optional[str] = None
    cash_out_date: Optional[str] = None
    order_total_amount: Optional[float] = None
    order_fee_amount: Optional[float] = None
    item_amount: Optional[float] = None
    order_state: Optional[str] = None
    cash_out_state: Optional[str] = None
    
    payment_means: Optional[str] = None
    installment_number: Optional[int] = None
    
    country: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zipcode: Optional[str] = None
    
    form_name: Optional[str] = None
    
    organization_name: Optional[str] = None
    organization_slug: Optional[str] = None
    
    item_type: Optional[str] = None
    item_name: Optional[str] = None
    item_state: Optional[str] = None
    
    payment_receipt_url: Optional[str] = None
    
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    emergency_contact: Optional[Dict[str, Any]] = None
    
    has_refund: bool = False
