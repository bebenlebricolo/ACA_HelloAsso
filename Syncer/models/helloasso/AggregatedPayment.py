from dataclasses import dataclass, field
from typing import List, Optional

from .CustomField import CustomField

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