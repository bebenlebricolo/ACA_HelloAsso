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
from typing import Any, Dict, List, Optional

import aiohttp

# required for SSL certificate verification on some systems
import ssl
import certifi

# Set the SSL context to use the certifi bundle
ssl_context = ssl.create_default_context(cafile=certifi.where())

from .client import HelloAssoClient
from .settings import (
    DEFAULT_CONCURRENCY,
    DEFAULT_OUTPUT_DIR,
    MAX_RETRIES,
    REQUEST_DELAY,
    RETRY_DELAY,
    Settings,
)
from .export import export_to_csv
from .models import AggregatedPayment, AuthConfig, CustomField, OrderDetails, PaymentState, RawPayment
from .reporter import Reporter


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
                       organization_slug: str,
                       *,
                       reporter: Optional[Reporter] = None,
                       index: int = 1,
                       total_forms: int = 1) -> Path:
    """Process a form and generate its CSV"""
    reporter = reporter or Reporter()
    reporter.form_started(form_slug, index, total_forms)

    # 1. Retrieve all payments for this form
    reporter.log(f"  Récupération des paiements...")
    raw_payments = await client.get_all_payments(form_slug, organization_slug)
    reporter.log(f"  Trouvés: {len(raw_payments)} paiements")

    if not raw_payments:
        reporter.log(f"  Aucune donnée à exporter pour {form_slug}")
        reporter.form_finished(form_slug, Path())
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
    reporter.log(f"  Récupération des détails des commandes ({form_slug})...")

    completed = 0

    async def fetch_and_aggregate(payment) -> AggregatedPayment:
        nonlocal completed
        order_details_data = await client.get_order_details(payment.order.id)
        order_details = parse_order_details(order_details_data)
        aggregated = aggregate_payment(payment, order_details)
        completed += 1
        reporter.payment_progress(form_slug, completed, total)
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

    reporter.log(f"    [{total}/{total}] Terminée ({form_slug})")

    # 4. Export to CSV
    reporter.log(f"  Export vers CSV...")
    output_path = export_to_csv(list(aggregated_payments), form_slug, output_dir)
    reporter.log(f"  Fichier généré: {output_path}")

    reporter.form_finished(form_slug, output_path)
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
        required=True,
        help="Slug de l'organisation HelloAsso"
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

        config = AuthConfig()
        config.load_from_file(config_path)
        if args.verbose:
            print(f"Configuration chargée: {config.client_id[:8]}...")
    except ValueError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)

    # Load settings, if any





    forms_to_process = resolve_forms(args.forms, settings)
    if not forms_to_process:
        print("Aucune billetterie à traiter!", file=sys.stderr)
        sys.exit(1)


    settings = Settings(
        request_delay=args.request_delay,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        concurrency=args.concurrency,
        sequential=args.sequential,
        output_dir=Path(args.output),
        organization=args.organization,
        save_to_user_config=True
    )

    # Dry run: only report what would be done, no network calls.
    if args.dry_run:
        for form_slug in forms_to_process:
            print(f"[DRY RUN] Traiterait: {form_slug}")
        return

    asyncio.run(sync_forms(forms_to_process, Path(args.output), args.organization, settings, config))


def resolve_forms(forms: List[str]) -> List[str]:
    """Expand the 'all' keyword to the known FORMS list."""
    if "all" in forms:
        return list(FORMS)
    return list(forms)


async def sync_forms(forms: List[str],
                     output_dir: Path,
                     organization: str,
                     settings: Settings,
                     config: AuthConfig,
                     reporter: Optional[Reporter] = None) -> List[str]:
    """Asynchronous orchestration: authentication then processing of the forms.

    Returns the list of generated CSV file paths. Progress and messages go
    through ``reporter`` (default: prints to the console).
    """
    reporter = reporter or Reporter()
    started_at = time.time()

    mode = "séquentiel (debug)" if settings.sequential else f"parallèle (concurrency={settings.concurrency})"
    reporter.log(f"Mode d'exécution: {mode}")

    generated_files: List[str] = []
    total_forms = len(forms)

    # Uses Certifi for SSL certificate verification
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = HelloAssoClient(session, settings)

        # 1. Authentication (initial sequential step)
        try:
            reporter.log("Authentification auprès de HelloAsso...")
            await client.authenticate(config)
            reporter.log("Authentification réussie!")
        except Exception as e:
            reporter.log(f"Erreur d'authentification: {e}")
            raise

        # 2. Process each form (in parallel, except in sequential mode)
        if settings.sequential:
            for index, form_slug in enumerate(forms, 1):
                if reporter.should_cancel():
                    reporter.log("Annulation demandée, arrêt.")
                    break
                try:
                    output_path = await process_form(
                        client, form_slug, output_dir, organization,
                        reporter=reporter, index=index, total_forms=total_forms)
                    if output_path and output_path != Path():
                        generated_files.append(str(output_path))
                except Exception as e:
                    reporter.log(f"Erreur lors du traitement de {form_slug}: {e}")
                    raise
        else:
            results = await asyncio.gather(
                *(process_form(client, form_slug, output_dir, organization,
                               reporter=reporter, index=index, total_forms=total_forms)
                  for index, form_slug in enumerate(forms, 1)),
                return_exceptions=True,
            )
            for form_slug, result in zip(forms, results):
                if isinstance(result, Exception):
                    reporter.log(f"Erreur lors du traitement de {form_slug}: {result}")
                    raise result
                if result and result != Path():
                    generated_files.append(str(result))

    # Summary
    reporter.log(f"\n{'='*60}")
    reporter.log("Résumé:")
    reporter.log(f"  Billetteries traitées: {total_forms}")
    reporter.log(f"  Fichiers générés: {len(generated_files)}")
    for f in generated_files:
        reporter.log(f"    - {f}")
    reporter.log(f"{'='*60}")

    final_duration = time.time() - started_at
    reporter.log(f"Durée totale: {final_duration:.2f} secondes")

    reporter.run_finished(generated_files)
    return generated_files


if __name__ == "__main__":
    main()
