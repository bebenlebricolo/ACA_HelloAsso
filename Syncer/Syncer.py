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
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import aiohttp

from client import HelloAssoClient
from config import (
    DEFAULT_CONCURRENCY,
    DEFAULT_OUTPUT_DIR,
    FORMS,
    MAX_RETRIES,
    ORGANIZATION_SLUG,
    REQUEST_DELAY,
    RETRY_DELAY,
    Settings,
    load_config,
)
from export import export_to_csv
from models import AggregatedPayment, AuthConfig, CustomField, OrderDetails, PaymentState, RawPayment


# =============================================================================
# Parsing & transforms
# =============================================================================


def cents_to_euros(cents: int) -> float:
    """Convert amount from cents to euros"""
    return cents / 100.0


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

    if payment.order:
        form_slug = payment.order.formSlug or form_slug

    if order_details:
        form_slug = order_details.formSlug or form_slug

    # Retrieve custom fields from the first item in order_details if available
    custom_fields = order_details.items[0].custom_fields
    custom_fields = post_process_custom_fields(custom_fields)

    return AggregatedPayment(
        # Payment identifiers
        payment_id=payment.id,

        # Timestamps
        payment_date=payment.date,

        # Amounts (converted to euros)
        payment_amount=cents_to_euros(payment.amount),

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


# =============================================================================
# Orchestration
# =============================================================================


async def process_form(client: HelloAssoClient,
                       form_slug: str,
                       output_dir: Path,
                       organization_slug: str = ORGANIZATION_SLUG) -> Path:
    """Process a form and generate its CSV"""
    print(f"\n{'='*60}")
    print(f"Traitement de la billetterie: {form_slug}")
    print(f"{'='*60}")

    # 1. Retrieve all payments for this form
    print(f"  Récupération des paiements...")
    raw_payments = await client.get_all_payments(form_slug, organization_slug)
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
        order_details_data = await client.get_order_details(payment.order.id)
        order_details = parse_order_details(order_details_data)
        aggregated = aggregate_payment(payment, order_details)
        completed += 1
        print(f"\t[{completed}/{total}] Commande {payment.order.id} traitée ({form_slug})...", end="\r")
        return aggregated

    if client.settings.sequential:
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

    settings = Settings(
        request_delay=args.request_delay,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        concurrency=args.concurrency,
        sequential=args.sequential,
    )

    mode = "séquentiel (debug)" if settings.sequential else f"parallèle (concurrency={settings.concurrency})"
    print(f"Mode d'exécution: {mode}")

    async with aiohttp.ClientSession() as session:
        client = HelloAssoClient(session, settings)

        # 1. Authentication (initial sequential step)
        try:
            print("Authentification auprès de HelloAsso...")
            await client.authenticate(config)
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
        elif settings.sequential:
            for form_slug in forms_to_process:
                try:
                    output_path = await process_form(client, form_slug, output_dir, args.organization)
                    if output_path and output_path != Path():
                        generated_files.append(str(output_path))
                except Exception as e:
                    print(f"Erreur lors du traitement de {form_slug}: {e}", file=sys.stderr)
                    raise
        else:
            results = await asyncio.gather(
                *(process_form(client, form_slug, output_dir, args.organization)
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
