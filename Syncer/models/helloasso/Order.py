from .Parseable import Parseable

from dataclasses import dataclass
from typing import Any, Dict, Optional


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