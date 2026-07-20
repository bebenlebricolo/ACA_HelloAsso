"""
CSV export of aggregated payments (one file per form).
"""

import csv
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .models import AggregatedPayment


def payment_to_csv_row(payment: AggregatedPayment) -> Dict[str, Any]:
    """Convert an aggregated payment into a flat dictionary for CSV"""

    row = {
        "payment_id": payment.payment_id,
        "payment_date": payment.payment_date,
        "payment_amount": payment.payment_amount,
        "first_name": payment.first_name,
        "last_name": payment.last_name,
        "email": payment.email,
        "form_slug": payment.form_slug,
        "payment_receipt_url": payment.payment_receipt_url or "",
    }

    # Adding custom fields to the row (flattened out, should be the same headers for all rows)
    custom_fields_dict = {}
    if payment.custom_fields:
        for field in payment.custom_fields:
            custom_fields_dict[field.name] = field.answer
        row.update(custom_fields_dict)

    return row


def get_csv_headers(payments: List[AggregatedPayment]) -> List[str]:
    """Generate the CSV headers based on the available data"""
    # Get keys from AggregatedPayment dataclass
    known_fields = [f.name for f in fields(AggregatedPayment)]
    additional_fields = []

    # should not happen
    if len(payments) == 0:
        return []

    # Get all custom fields (deduplicated) from all payments
    all_custom_fields = set()
    for payment in payments:
        for field in payment.custom_fields:
            all_custom_fields.add(field.name)

    additional_fields.extend(sorted(all_custom_fields))

    # Remove custom_fields from known fields
    known_fields.remove("custom_fields")
    return known_fields + additional_fields


def export_to_csv(payments: List[AggregatedPayment], form_slug: str, output_dir: Path) -> Path:
    """Export the payments to a CSV file"""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{form_slug}_{timestamp}.csv"
    output_path = output_dir / filename

    headers = get_csv_headers(payments)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()

        for payment in payments:
            row = payment_to_csv_row(payment)
            writer.writerow(row)

    return output_path
