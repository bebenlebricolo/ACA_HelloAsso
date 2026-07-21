from dataclasses import dataclass
from typing import Any, Dict, Optional

from .Parseable import Parseable

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