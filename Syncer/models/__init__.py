"""
Models package for HelloAsso Syncer
Contains all dataclasses for data representation
"""

from .schemas import (
    AuthConfig,
    RawPayment,
    OrderDetails,
    AggregatedPayment,
    Payer,
    Item,
    Order,
)

__all__ = [
    "AuthConfig",
    "RawPayment",
    "OrderDetails",
    "AggregatedPayment",
    "Payer",
    "Item",
    "Order",
]
