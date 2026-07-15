"""
Data schemas for HelloAsso Syncer

This module contains all dataclasses used to represent:
- Authentication configuration
- Payment data from HelloAsso API
- Order details
- Aggregated payment data (payment + order details joined)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AuthConfig:
    """Configuration d'authentification HelloAsso"""
    client_id: str
    client_secret: str


@dataclass
class Payment:
    """Représente un paiement depuis l'API HelloAsso"""
    id: int
    form_slug: str
    form_type: str
    date: str
    amount: float
    state: str
    payer_first_name: str
    payer_last_name: str
    payer_email: str
    order_id: int
    items: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderDetails:
    """Représente les détails d'une commande HelloAsso"""
    id: int
    form_slug: str
    form_type: str
    date: str
    amount: float
    state: str
    total_amount: float
    fee_amount: float
    payer_first_name: str
    payer_last_name: str
    payer_email: str
    payer_phone: Optional[str] = None
    payer_address: Optional[str] = None
    payer_city: Optional[str] = None
    payer_zipcode: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    emergency_contact: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedPayment:
    """Paiement agrégé avec toutes les informations (payment + order details)"""
    # Données du paiement
    payment_id: int
    payment_date: str
    payment_amount: float
    payment_state: str

    # Données de l'ordre
    order_id: int
    order_date: str
    order_total_amount: float
    order_fee_amount: float
    order_state: str

    # Informations du payeur
    first_name: str
    last_name: str
    email: str

    # Billetterie
    form_slug: str
    form_type: str

    # Informations du payeur (optionnelles)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zipcode: Optional[str] = None

    # Items commandés
    items: List[Dict[str, Any]] = field(default_factory=list)

    # Champs personnalisés et metadata
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Contact d'urgence
    emergency_contact: Optional[Dict[str, Any]] = None
