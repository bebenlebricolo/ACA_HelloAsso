#!/usr/bin/env python3
"""
HelloAsso Syncer - Synchronisation des paiements et adhésions

Ce script permet de :
1. S'authentifier auprès de l'API HelloAsso
2. Récupérer les paiements pour une liste de billetteries
3. Récupérer les détails de chaque ordre/paiement
4. Agréger les données et générer un CSV par billetterie

Utilisation:
    python Syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26
    python Syncer.py --forms all  # Tous les forms de type Membership
    python Syncer.py --config secrets.json --forms licence-saison-aviron-sante-25-26
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from models import AuthConfig, RawPayment, OrderDetails, AggregatedPayment, Payer, Item, Order


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent / "secrets.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_API_URL = "https://api.helloasso.com"

# Organisation (à adapter si besoin)
ORGANIZATION_SLUG = "aviron-club-angouleme"

# Type de formulaire
FORM_CATEGORY = "Membership"

# Rate limiting
REQUEST_DELAY = 0.1  # Délai entre les requêtes (secondes)
MAX_RETRIES = 3
RETRY_DELAY = 2  # secondes


# =============================================================================
# Helper Functions
# =============================================================================

def load_config(config_path: Optional[Path] = None) -> AuthConfig:
    """Charge la configuration depuis un fichier JSON ou les variables d'environnement"""

    # Essayer variables d'environnement d'abord
    client_id = os.getenv("HELLOASSO_CLIENT_ID")
    client_secret = os.getenv("HELLOASSO_CLIENT_SECRET")

    if client_id and client_secret:
        return AuthConfig(client_id=client_id, client_secret=client_secret)

    # Sinon, charger depuis le fichier
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


def get_access_token(config: AuthConfig) -> str:
    """Récupère un token d'accès OAuth2"""
    url = f"{BASE_API_URL}/oauth2/token"

    payload = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "grant_type": "client_credentials"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            access_token = data.get("access_token")

            if not access_token:
                raise ValueError(
                    f"Pas de token d'accès dans la réponse: {data}")

            return access_token

        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY * (attempt + 1))

    raise RuntimeError("Impossible d'obtenir le token d'accès")


def get_all_payments(
    access_token: str,
    form_slug: str,
    organization_slug: str = ORGANIZATION_SLUG,
    form_type: str = FORM_CATEGORY,
    page_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Récupère tous les paiements pour une billetterie donnée (avec pagination)

    L'API HelloAsso utilise une pagination avec page et limit
    """
    url = f"{BASE_API_URL}/v5/organizations/{organization_slug}/forms/{form_type}/{form_slug}/payments"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    all_payments = []
    page = 1

    while True:
        params = {
            "page": page,
            "limit": page_size
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            payments = data.get("data", [])

            if not payments:
                break

            all_payments.extend(payments)

            # Vérifier s'il y a une page suivante
            # L'API retourne souvent un total_count ou un has_more
            if len(payments) < page_size:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        except requests.exceptions.RequestException as e:
            print(
                f"Erreur lors de la récupération des paiements (page {page}): {e}")
            break

    return all_payments


def get_order_details(access_token: str, order_id: int) -> Dict[str, Any]:
    """Récupère les détails d'une commande spécifique"""
    url = f"{BASE_API_URL}/v5/orders/{order_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "HelloAsso-Syncer/1.0"
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                print(
                    f"Erreur lors de la récupération des détails de la commande {order_id}: {e}")
                return {}
            time.sleep(RETRY_DELAY * (attempt + 1))

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


def parse_items(item_data: List[Dict[str, Any]] | None) -> Optional[List[Item]]:
    """Parse items from API response"""
    if not item_data:
        return None

    items = []
    for item in item_data:
        if item is None:
            continue

        current = Item()
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


def extract_emergency_contact(custom_fields: Any) -> Optional[Dict[str, Any]]:
    """Extract emergency contact from customFields"""
    if custom_fields is None:
        return None

    emergency_contact = None

    if isinstance(custom_fields, list):
        for field in custom_fields:
            if isinstance(field, dict):
                name = field.get("name", "").lower()
                if "urgence" in name or "emergency" in name:
                    emergency_contact = field
                    break

    elif isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            if isinstance(value, dict) and ("urgence" in key.lower() or "emergency" in key.lower()):
                emergency_contact = value
                break

    return emergency_contact


def parse_order_details(order_data: Dict[str, Any]) -> OrderDetails:
    """Parse detailed order information from /orders/{id} endpoint"""
    order_details = OrderDetails()
    order_details.from_raw(order_data)
    return order_details


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

    # Determine has_refund
    custom_fields = order_details.items[0].custom_fields

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

        #payment_means=payment.paymentMeans,

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
    """Aplatit un dictionnaire imbriqué pour l'export CSV"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Pour les listes, on crée des colonnes séparées
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
    """Convertit un paiement agrégé en dictionnaire plat pour CSV"""

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
    """Génère les en-têtes CSV en fonction des données disponibles"""
    # Get keys from AggregatedPayment dataclass
    known_fields = [f.name for f in fields(AggregatedPayment)]
    additional_fields = []
    for field in payments[0].custom_fields:
        additional_fields.append(field.name)

    known_fields.remove("custom_fields")  # Remove custom_fields from known fields
    return known_fields + additional_fields


def export_to_csv(payments: List[AggregatedPayment], form_slug: str, output_dir: Path) -> Path:
    """Exporte les paiements vers un fichier CSV"""
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


def get_all_forms(access_token: str, organization_slug: str = ORGANIZATION_SLUG) -> List[str]:
    """Récupère tous les forms de type Membership pour l'organisation"""
    url = f"{BASE_API_URL}/v5/organizations/{organization_slug}/forms"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        forms = data.get("data", [])

        # Filtrer sur les forms de type Membership
        membership_forms = [
            form.get("slug")
            for form in forms
            if form.get("type") == FORM_CATEGORY
        ]

        return membership_forms

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des forms: {e}")
        return []


# =============================================================================
# Main Function
# =============================================================================

def process_form(
    access_token: str,
    form_slug: str,
    output_dir: Path,
    organization_slug: str = ORGANIZATION_SLUG
) -> Path:
    """Traite une billetterie et génère son CSV"""
    print(f"\n{'='*60}")
    print(f"Traitement de la billetterie: {form_slug}")
    print(f"{'='*60}")

    # 1. Récupérer tous les paiements pour cette billetterie
    print(f"  Récupération des paiements...")
    raw_payments = get_all_payments(access_token, form_slug, organization_slug)
    print(f"  Trouvés: {len(raw_payments)} paiements")

    if not raw_payments:
        print(f"  Aucune donnée à exporter pour {form_slug}")
        return Path()

    # 2. Parser les paiements
    payments = []
    for p in raw_payments:
        single_p = parse_payment(p)
        payments.append(single_p)

    # 3. Pour chaque paiement, récupérer les détails de la commande
    aggregated_payments = []
    print(f"  Récupération des détails des commandes...")

    for i, payment in enumerate(payments):
        # Get order_id from payment.order.id if available
        order_id = payment.order.id
        print(
            f"    [{i+1}/{len(payments)}] Récupération détails commande {order_id}...", end="\r")

        order_details_data = get_order_details(access_token, order_id)

        order_details = parse_order_details(order_details_data)
        aggregated = aggregate_payment(payment, order_details)
        aggregated_payments.append(aggregated)

        time.sleep(REQUEST_DELAY)

    print(f"    [{len(payments)}/{len(payments)}] Terminée")

    # 4. Exporter vers CSV
    print(f"  Export vers CSV...")
    output_path = export_to_csv(aggregated_payments, form_slug, output_dir)
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

    # Charger la configuration
    try:
        config_path = Path(args.config) if args.config else None
        config = load_config(config_path)
        if args.verbose:
            print(f"Configuration chargée: {config.client_id[:8]}...")
    except ValueError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)

    # Obtenir le token d'accès
    try:
        print("Authentification auprès de HelloAsso...")
        access_token = get_access_token(config)
        print("Authentification réussie!")
    except Exception as e:
        print(f"Erreur d'authentification: {e}", file=sys.stderr)
        sys.exit(1)

    # Déterminer la liste des billetteries à traiter
    output_dir = Path(args.output)
    forms_to_process = []

    if "all" in args.forms:
        print("\nRécupération de toutes les billetteries Membership...")
        all_forms = get_all_forms(access_token, args.organization)
        print(f"Trouvées {len(all_forms)} billetteries:")
        for f in all_forms:
            print(f"  - {f}")
        forms_to_process = all_forms
    else:
        forms_to_process = args.forms

    if not forms_to_process:
        print("Aucune billetterie à traiter!", file=sys.stderr)
        sys.exit(1)

    # Traiter chaque billetterie
    generated_files = []

    for form_slug in forms_to_process:
        if args.dry_run:
            print(f"[DRY RUN] Traiterait: {form_slug}")
            continue

        try:
            output_path = process_form(
                access_token, form_slug, output_dir, args.organization
            )
            if output_path:
                generated_files.append(str(output_path))
        except Exception as e:
            print(
                f"Erreur lors du traitement de {form_slug}: {e}", file=sys.stderr)

    # Résumé
    print(f"\n{'='*60}")
    print("Résumé:")
    print(f"  Billetteries traitées: {len(forms_to_process)}")
    if not args.dry_run:
        print(f"  Fichiers générés: {len(generated_files)}")
        for f in generated_files:
            print(f"    - {f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
