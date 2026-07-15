"""
Models package for HelloAsso Syncer
Contains all dataclasses for data representation
"""

from .schemas import (
    AuthConfig,
    Payment,
    OrderDetails,
    AggregatedPayment,
)

__all__ = [
    "AuthConfig",
    "Payment",
    "OrderDetails",
    "AggregatedPayment",
]
