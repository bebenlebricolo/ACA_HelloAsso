#!/usr/bin/env python3
"""
HelloAsso Syncer - Synchronization of payments and memberships

This script allows to:
1. Authenticate against the HelloAsso API
2. Retrieve payments for a list of forms
3. Retrieve the details of each order/payment
4. Aggregate the data and generate one CSV per form

Usage:
    python Syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26
    python Syncer.py --forms all  # All Membership forms
    python Syncer.py --config secrets.json --forms licence-saison-aviron-sante-25-26
"""

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiohttp
from models import AuthConfig, RawPayment, OrderDetails, AggregatedPayment, Payer, PaymentItem, Order, OrderState, PaymentState, CustomField


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent / "secrets.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_API_URL = "https://api.helloasso.com"

# Organization (adapt if needed)
ORGANIZATION_SLUG = "aviron-club-angouleme"

# Form type
FORM_CATEGORY = "Membership"

# Rate limiting (defaults, overridable via CLI)
REQUEST_DELAY = 0.1  # Delay between requests (seconds)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
DEFAULT_CONCURRENCY = 5  # Maximum concurrent requests

USER_AGENT = "HelloAsso-Syncer/1.0"


# =============================================================================
# Runtime context (shared across all async tasks)
# =============================================================================


@dataclass
class RuntimeConfig:
    """Execution context shared across the asynchronous tasks.

    Carries the shared HTTP session, the concurrency-limiting semaphore
    and the throttling / retry parameters.
    """

    session: aiohttp.ClientSession
    semaphore: asyncio.Semaphore
    request_delay: float = REQUEST_DELAY
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    sequential: bool = False


class HttpError(Exception):
    """Non-recoverable HTTP error after all retries have been exhausted."""


async def request_json(cfg: RuntimeConfig,
                       method: str,
                       url: str,
                       *,
                       expected_status: int = 200,
                       **kwargs: Any) -> Dict[str, Any]:
    """Perform an HTTP request returning JSON, with throttling and retries.

    - Acquires the semaphore to bound the number of concurrent requests.
    - Applies a delay (with a small jitter) to space out calls and reduce
      the risk of being flagged by the API.
    - Retries with exponential backoff and honors the ``Retry-After`` header
      returned on a ``429`` (Too Many Requests) status.
    """
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)

    last_error: Optional[Exception] = None

    for attempt in range(cfg.max_retries):
        async with cfg.semaphore:
            # Throttle: space out calls (jitter to avoid a regular pattern)
            if cfg.request_delay > 0:
                jitter = random.uniform(0, cfg.request_delay * 0.25)
                await asyncio.sleep(cfg.request_delay + jitter)

            try:
                async with cfg.session.request(method, url, headers=headers, **kwargs) as response:
                    # Explicit rate limiting: honor Retry-After
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", cfg.retry_delay))
                        last_error = HttpError(f"429 Too Many Requests sur {url}")
                        if attempt < cfg.max_retries - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        raise last_error

                    response.raise_for_status()

                    if response.status != expected_status:
                        raise HttpError(
                            f"Statut inattendu {response.status} (attendu {expected_status}) sur {url}")

                    return await response.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt == cfg.max_retries - 1:
                    raise
                await asyncio.sleep(cfg.retry_delay * (attempt + 1))

    raise HttpError(f"Échec de la requête {method} {url}: {last_error}")

# Forms of interest (can be overridden by command line arguments)
FORMS = [
    "licence-jeunes-saison-25-26",
    "licence-saison-25-26-loisirs",
    "adhesion-2026-2027-sport-sante-1",
    "licence-saison-aviron-sante-25-26",
]

# =============================================================================
# Helper Functions
# =============================================================================


def load_config(config_path: Optional[Path] = None) -> AuthConfig:
    """Load the configuration from a JSON file or environment variables"""

    # Try environment variables first
    client_id = os.getenv("HELLOASSO_CLIENT_ID")
    client_secret = os.getenv("HELLOASSO_CLIENT_SECRET")

    if client_id and client_secret:
        return AuthConfig(client_id=client_id, client_secret=client_secret)

    # Otherwise, load from the file
    config_paths = []
    if config_path:
        config_paths.append(config_path)
    if DEFAULT_CONFIG_PATH.exists():
        config_paths.append(DEFAULT_CONFIG_PATH)

    for path in config_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return AuthConfig(
                    client_id=data.get("clientId") or data.get("client_id"),
                    client_secret=data.get(
                        "clientSecret") or data.get("client_secret")
                )
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            continue

    raise ValueError(
        "Impossible de trouver la configuration. "
        "Fournissez un fichier secrets.json ou définissez les variables d'environnement "
        "HELLOASSO_CLIENT_ID et HELLOASSO_CLIENT_SECRET."
    )

async def get_access_token(cfg: RuntimeConfig, config: AuthConfig) -> str:
    """Retrieve an OAuth2 access token (initial sequential step)"""
    url = f"{BASE_API_URL}/oauth2/token"

    payload = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "grant_type": "client_credentials"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = await request_json(cfg, "POST", url, data=payload, headers=headers)
    access_token = data.get("access_token")

    if not access_token:
        raise ValueError(f"Pas de token d'accès dans la réponse: {data}")

    return access_token

async def get_all_payments(cfg: RuntimeConfig,
                           access_token: str,
                           form_slug: str,
                           organization_slug: str = ORGANIZATION_SLUG,
                           form_type: str = FORM_CATEGORY,
                           page_size: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve all payments for a given form (with pagination)

    Pagination stays sequential because the number of pages is only known
    once a partial/empty page is received. Each page request still goes
    through the concurrency limiter (request_json).
    """
    url = f"{BASE_API_URL}/v5/organizations/{organization_slug}/forms/{form_type}/{form_slug}/payments"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    all_payments = []
    page = 1

    while True:
        params = {
            "page": page,
            "limit": page_size
        }

        try:
            data = await request_json(cfg, "GET", url, headers=headers, params=params)
        except (aiohttp.ClientError, HttpError, asyncio.TimeoutError) as e:
            print(f"Erreur lors de la récupération des paiements (page {page}): {e}")
            break

        payments = data.get("data", [])

        if not payments:
            break

        all_payments.extend(payments)

        # Last page reached (partial page)
        if len(payments) < page_size:
            break

        page += 1

    return all_payments

async def get_order_details(cfg: RuntimeConfig, access_token: str, order_id: int) -> Dict[str, Any]:
    """Retrieve the details of a specific order"""
    url = f"{BASE_API_URL}/v5/orders/{order_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        return await request_json(cfg, "GET", url, headers=headers)
    except (aiohttp.ClientError, HttpError, asyncio.TimeoutError) as e:
        print(f"Erreur lors de la récupération des détails de la commande {order_id}: {e}")
        return {}

def cents_to_euros(cents: int) -> float:
    """Convert amount from cents to euros"""
    return cents / 100.0

def parse_payer(payer_data: Dict[str, Any] | None) -> Optional[Payer]:
    """Parse payer information from API response"""
    if not payer_data:
        return None

    return Payer(
        email=payer_data.get("email", ""),
        country=payer_data.get("country"),
        firstName=payer_data.get("firstName"),
        lastName=payer_data.get("lastName"),
        address=payer_data.get("address"),
        city=payer_data.get("city"),
        zipcode=payer_data.get("zipcode"),
    )

def parse_items(item_data: List[Dict[str, Any]] | None) -> Optional[List[PaymentItem]]:
    """Parse items from API response"""
    if not item_data:
        return None

    items = []
    for item in item_data:
        if item is None:
            continue

        current = PaymentItem()
        current.from_raw(item)
        items.append(current)
    return items

def parse_order(order_data: Dict[str, Any] | None) -> Optional[Order]:
    """Parse order information from API response"""
    if not order_data:
        return None

    return Order(
        id=order_data.get("id", 0),
        date=order_data.get("date"),
        formSlug=order_data.get("formSlug"),
        formType=order_data.get("formType"),
        formName=order_data.get("formName"),
        organizationName=order_data.get("organizationName"),
        organizationSlug=order_data.get("organizationSlug"),
        organizationType=order_data.get("organizationType"),
        organizationIsUnderColucheLaw=order_data.get(
            "organizationIsUnderColucheLaw"),
        meta=order_data.get("meta"),
        isAnonymous=order_data.get("isAnonymous"),
        isAmountHidden=order_data.get("isAmountHidden"),
    )

def parse_payment(payment_data: Dict[str, Any]) -> RawPayment:
    """Parse raw payment data from /payments endpoint"""
    raw_payment = RawPayment()
    raw_payment.from_raw(payment_data)
    return raw_payment

def parse_order_details(order_data: Dict[str, Any]) -> OrderDetails:
    """Parse detailed order information from /orders/{id} endpoint"""
    order_details = OrderDetails()
    order_details.from_raw(order_data)
    return order_details

def post_process_custom_fields(custom_fields: List[CustomField]) -> List[CustomField]:
    for field in custom_fields:
        if field.name == "Téléphone" :
            # Clean up the phone number
            if field.answer is not None:
                # Detect formats
                # full 07 00 00 00 00
                # or compact 700000000

                # Full format is the target format we expect
                cleaned_number = field.answer.strip().replace(" ", "").replace("-", "")
                if cleaned_number.startswith("0") and len(cleaned_number) == 10:
                    pass # Already in correct format
                elif cleaned_number.startswith("7") or cleaned_number.startswith("6") and len(cleaned_number) == 9:
                    cleaned_number = "0" + cleaned_number
                else:
                    cleaned_number = field.answer  # Keep as is if format is unexpected

                # Insert a space every 2 digits for readability
                formatted_number = ""
                for i in range(0, 5):
                    formatted_number += cleaned_number[i*2:(i+1)*2] + " "

                field.answer = formatted_number.rstrip()  # Remove trailing space
                continue  # Move to next field after processing phone number

        if field.name == "Mail des parents" :
            if field.answer is not None:
                field.answer = field.answer.strip().lower() # Lowercased emails
            continue  # Move to next field after processing phone number

    return custom_fields



def aggregate_payment(payment: RawPayment, order_details: OrderDetails) -> AggregatedPayment:
    """Aggregate payment and order details into a single structure for CSV export"""
    # Extract payer info (prefer order_details payer as it's more complete)
    payer = order_details.payer if order_details and order_details.payer else payment.payer

    first_name = ""
    last_name = ""
    email = ""

    if payer:
        first_name = payer.firstName or ""
        last_name = payer.lastName or ""
        email = payer.email or ""

    # Extract form info
    form_slug = payment.formSlug or ""
    form_type = payment.formType or ""

    if payment.order:
        form_slug = payment.order.formSlug or form_slug
        form_type = payment.order.formType or form_type

    if order_details:
        form_slug = order_details.formSlug or form_slug
        form_type = order_details.formType or form_type

    # Retrieve custom fields from the first item in order_details if available
    custom_fields = order_details.items[0].custom_fields
    custom_fields = post_process_custom_fields(custom_fields)


    # Extract metadata
    metadata = {}
    if payment.meta:
        metadata.update(payment.meta)

    return AggregatedPayment(
        # Payment identifiers
        payment_id=payment.id,

        # Timestamps
        payment_date=payment.date,

        # Amounts (converted to euros)
        payment_amount=cents_to_euros(payment.amount),

        # payment_means=payment.paymentMeans,

        # Payer information
        first_name=first_name,
        last_name=last_name,
        email=email,

        # Form information
        form_slug=form_slug,

        # URLs
        payment_receipt_url=payment.paymentReceiptUrl,

        # Custom fields and metadata
        custom_fields=custom_fields,
    )

def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Flatten a nested dictionary for CSV export"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, create separate columns
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(
                        item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, v))

    return dict(items)

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
    if len(payments) == 0 :
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

async def get_all_forms(cfg: RuntimeConfig, access_token: str, organization_slug: str = ORGANIZATION_SLUG) -> List[str]:
    """Retrieve all Membership forms for the organization"""
    url = f"{BASE_API_URL}/v5/organizations/{organization_slug}/forms"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        data = await request_json(cfg, "GET", url, headers=headers)
    except (aiohttp.ClientError, HttpError, asyncio.TimeoutError) as e:
        print(f"Erreur lors de la récupération des forms: {e}")
        return []

    forms = data.get("data", [])

    # Filter on Membership forms
    membership_forms = [
        form.get("slug")
        for form in forms
        if form.get("type") == FORM_CATEGORY
    ]

    return membership_forms

# =============================================================================
# Main Function
# =============================================================================

async def process_form(cfg: RuntimeConfig,
                       access_token: str,
                       form_slug: str,
                       output_dir: Path,
                       organization_slug: str = ORGANIZATION_SLUG) -> Path:
    """Process a form and generate its CSV"""
    print(f"\n{'='*60}")
    print(f"Traitement de la billetterie: {form_slug}")
    print(f"{'='*60}")

    # 1. Retrieve all payments for this form
    print(f"  Récupération des paiements...")
    raw_payments = await get_all_payments(cfg, access_token, form_slug, organization_slug)
    print(f"  Trouvés: {len(raw_payments)} paiements")

    if not raw_payments:
        print(f"  Aucune donnée à exporter pour {form_slug}")
        return Path()

    # 2. Parse the payments
    payments = []
    for p in raw_payments:
        single_p = parse_payment(p)

        # Skip failed payments
        if single_p.state != PaymentState.Authorized:
            continue
        payments.append(single_p)

    total = len(payments)

    # 3. For each payment, retrieve the order details.
    #    This is the most network-intensive step: we parallelize it (except
    #    in sequential mode), bounding the concurrency via the semaphore.
    print(f"  Récupération des détails des commandes ({form_slug})...")

    completed = 0

    async def fetch_and_aggregate(payment) -> AggregatedPayment:
        nonlocal completed
        order_details_data = await get_order_details(cfg, access_token, payment.order.id)
        order_details = parse_order_details(order_details_data)
        aggregated = aggregate_payment(payment, order_details)
        completed += 1
        print(f"\t[{completed}/{total}] Commande {payment.order.id} traitée ({form_slug})...", end="\r")
        return aggregated

    if cfg.sequential:
        # Debug mode: one order at a time, deterministic ordering
        aggregated_payments = []
        for payment in payments:
            aggregated_payments.append(await fetch_and_aggregate(payment))
    else:
        aggregated_payments = await asyncio.gather(
            *(fetch_and_aggregate(payment) for payment in payments)
        )

    # Clear line after loop
    print(" " * 80, end="\r")  # Clear the line
    print(f"    [{total}/{total}] Terminée ({form_slug})")

    # 4. Export to CSV
    print(f"  Export vers CSV...")
    output_path = export_to_csv(list(aggregated_payments), form_slug, output_dir)
    print(f"  Fichier généré: {output_path}")

    return output_path

def main():
    parser = argparse.ArgumentParser(
        description="Synchronisation des données HelloAsso - Aviron Club Angoulême",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
               Exemples:
               python Syncer.py --forms licence-saison-aviron-sante-25-26
               python Syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26
               python Syncer.py --forms all
               python Syncer.py --config /chemin/vers/secrets.json --forms all
            """
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Chemin vers le fichier de configuration secrets.json"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Dossier de sortie pour les fichiers CSV (par défaut: ./output)"
    )

    parser.add_argument(
        "--organization",
        type=str,
        default=ORGANIZATION_SLUG,
        help=f"Slug de l'organisation HelloAsso (par défaut: {ORGANIZATION_SLUG})"
    )

    parser.add_argument(
        "--forms", "-f",
        nargs='+',
        required=True,
        help="Liste des slugs de billetteries (kebab-case) ou 'all' pour toutes les billetteries Membership"
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Nombre maximum de requêtes simultanées (par défaut: {DEFAULT_CONCURRENCY})"
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=REQUEST_DELAY,
        help=f"Délai minimum (secondes) entre requêtes pour throttler (par défaut: {REQUEST_DELAY})"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Nombre de tentatives en cas d'erreur réseau (par défaut: {MAX_RETRIES})"
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=RETRY_DELAY,
        help=f"Délai de base (secondes) pour le backoff des retries (par défaut: {RETRY_DELAY})"
    )

    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Mode debug: exécute les requêtes une par une (aucune parallélisation)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode test: affiche ce qui serait fait sans générer de fichiers"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbeux"
    )

    args = parser.parse_args()

    # Load the configuration
    try:
        config_path = Path(args.config) if args.config else None
        config = load_config(config_path)
        if args.verbose:
            print(f"Configuration chargée: {config.client_id[:8]}...")
    except ValueError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(args, config))


async def run(args: argparse.Namespace, config: AuthConfig) -> None:
    """Asynchronous orchestration: authentication then processing of the forms."""

    output_dir = Path(args.output)
    started_at = time.time()

    mode = "séquentiel (debug)" if args.sequential else f"parallèle (concurrency={args.concurrency})"
    print(f"Mode d'exécution: {mode}")

    # A single shared HTTP session + a semaphore bounds the global concurrency
    # (across all forms combined).
    semaphore = asyncio.Semaphore(1 if args.sequential else max(1, args.concurrency))

    async with aiohttp.ClientSession() as session:
        cfg = RuntimeConfig(
            session=session,
            semaphore=semaphore,
            request_delay=args.request_delay,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            sequential=args.sequential,
        )

        # 1. Authentication (initial sequential step)
        try:
            print("Authentification auprès de HelloAsso...")
            access_token = await get_access_token(cfg, config)
            print("Authentification réussie!")
        except Exception as e:
            print(f"Erreur d'authentification: {e}", file=sys.stderr)
            raise

        # 2. Determine the list of forms to process
        if "all" in args.forms:
            print("\nRécupération de toutes les billetteries Membership...")
            forms_to_process = FORMS
            print(f"{len(forms_to_process)} billetteries seront utilisées:")
            for f in forms_to_process:
                print(f"  - {f}")
        else:
            forms_to_process = args.forms

        if not forms_to_process:
            print("Aucune billetterie à traiter!", file=sys.stderr)
            sys.exit(1)

        # 3. Process each form (in parallel, except in sequential mode)
        generated_files: List[str] = []

        if args.dry_run:
            for form_slug in forms_to_process:
                print(f"[DRY RUN] Traiterait: {form_slug}")
        elif cfg.sequential:
            for form_slug in forms_to_process:
                try:
                    output_path = await process_form(cfg, access_token, form_slug, output_dir, args.organization)
                    if output_path and output_path != Path():
                        generated_files.append(str(output_path))
                except Exception as e:
                    print(f"Erreur lors du traitement de {form_slug}: {e}", file=sys.stderr)
                    raise
        else:
            results = await asyncio.gather(
                *(process_form(cfg, access_token, form_slug, output_dir, args.organization)
                  for form_slug in forms_to_process),
                return_exceptions=True,
            )
            for form_slug, result in zip(forms_to_process, results):
                if isinstance(result, Exception):
                    print(f"Erreur lors du traitement de {form_slug}: {result}", file=sys.stderr)
                    raise result
                if result and result != Path():
                    generated_files.append(str(result))

    # Summary
    print(f"\n{'='*60}")
    print("Résumé:")
    print(f"  Billetteries traitées: {len(forms_to_process)}")
    if not args.dry_run:
        print(f"  Fichiers générés: {len(generated_files)}")
        for f in generated_files:
            print(f"    - {f}")
    print(f"{'='*60}")

    final_duration = time.time() - started_at
    print(f"Durée totale: {final_duration:.2f} secondes")


if __name__ == "__main__":
    main()
