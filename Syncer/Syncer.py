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
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests


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
# Data Classes
# =============================================================================

@dataclass
class AuthConfig:
    """Configuration d'authentification"""
    client_id: str
    client_secret: str


@dataclass
class Payment:
    """Représente un paiement depuis l'API HelloAsso"""
    id: int
    form_slug: str
    form_type: str
    date: str
    amount: float
    state: str
    payer_first_name: str
    payer_last_name: str
    payer_email: str
    order_id: int
    items: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderDetails:
    """Représente les détails d'une commande"""
    id: int
    form_slug: str
    form_type: str
    date: str
    amount: float
    state: str
    total_amount: float
    fee_amount: float
    payer_first_name: str
    payer_last_name: str
    payer_email: str
    payer_phone: Optional[str] = None
    payer_address: Optional[str] = None
    payer_city: Optional[str] = None
    payer_zipcode: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    emergency_contact: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedPayment:
    """Paiement agrégé avec toutes les informations"""
    # Données du paiement
    payment_id: int
    payment_date: str
    payment_amount: float
    payment_state: str

    # Données de l'ordre
    order_id: int
    order_date: str
    order_total_amount: float
    order_fee_amount: float
    order_state: str

    # Informations du payeur
    first_name: str
    last_name: str
    email: str

    # Billetterie
    form_slug: str
    form_type: str

    # Informations du payeur (optionnelles)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zipcode: Optional[str] = None

    # Items commandés
    items: List[Dict[str, Any]] = field(default_factory=list)

    # Champs personnalisés et metadata
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Contact d'urgence
    emergency_contact: Optional[Dict[str, Any]] = None


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
                    client_secret=data.get("clientSecret") or data.get("client_secret")
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
                raise ValueError(f"Pas de token d'accès dans la réponse: {data}")

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
            print(f"Erreur lors de la récupération des paiements (page {page}): {e}")
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
                print(f"Erreur lors de la récupération des détails de la commande {order_id}: {e}")
                return {}
            time.sleep(RETRY_DELAY * (attempt + 1))

    return {}


def parse_payment(payment_data: Dict[str, Any], form_slug: str) -> Payment:
    """Parse les données brutes d'un paiement"""
    return Payment(
        id=payment_data.get("id"),
        form_slug=form_slug,
        form_type=FORM_CATEGORY,
        date=payment_data.get("date"),
        amount=payment_data.get("amount", 0),
        state=payment_data.get("state"),
        payer_first_name=payment_data.get("payer", {}).get("firstName", ""),
        payer_last_name=payment_data.get("payer", {}).get("lastName", ""),
        payer_email=payment_data.get("payer", {}).get("email", ""),
        order_id=payment_data.get("orderId"),
        items=payment_data.get("items", []),
        custom_fields=payment_data.get("customFields", {}),
        metadata=payment_data.get("metadata", {})
    )


def parse_order_details(order_data: Dict[str, Any]) -> OrderDetails:
    """Parse les détails d'une commande"""
    payer = order_data.get("payer", {})

    # Extraire le contact d'urgence s'il existe
    emergency_contact = None
    for field in order_data.get("customFields", []):
        if isinstance(field, dict):
            name = field.get("name", "").lower()
            if "urgence" in name or "emergency" in name:
                emergency_contact = field
                break

    # Si customFields est un dict, chercher dedans
    if isinstance(order_data.get("customFields"), dict):
        custom_fields_dict = order_data.get("customFields", {})
        for key, value in custom_fields_dict.items():
            if isinstance(value, dict) and ("urgence" in key.lower() or "emergency" in key.lower()):
                emergency_contact = value
                break

    return OrderDetails(
        id=order_data.get("id"),
        form_slug=order_data.get("formSlug", ""),
        form_type=order_data.get("formType", ""),
        date=order_data.get("date"),
        amount=order_data.get("amount", 0),
        total_amount=order_data.get("totalAmount", 0),
        fee_amount=order_data.get("feeAmount", 0),
        state=order_data.get("state"),
        payer_first_name=payer.get("firstName", ""),
        payer_last_name=payer.get("lastName", ""),
        payer_email=payer.get("email", ""),
        payer_phone=payer.get("phone"),
        payer_address=payer.get("address"),
        payer_city=payer.get("city"),
        payer_zipcode=payer.get("zipcode"),
        items=order_data.get("items", []),
        custom_fields=order_data.get("customFields", {}),
        metadata=order_data.get("metadata", {}),
        emergency_contact=emergency_contact
    )


def aggregate_payment(payment: Payment, order_details: OrderDetails) -> AggregatedPayment:
    """Agrège les données d'un paiement et de sa commande détaillée"""
    return AggregatedPayment(
        payment_id=payment.id,
        payment_date=payment.date,
        payment_amount=payment.amount,
        payment_state=payment.state,

        order_id=payment.order_id or order_details.id,
        order_date=order_details.date or payment.date,
        order_total_amount=order_details.total_amount,
        order_fee_amount=order_details.fee_amount,
        order_state=order_details.state,

        first_name=order_details.payer_first_name or payment.payer_first_name,
        last_name=order_details.payer_last_name or payment.payer_last_name,
        email=order_details.payer_email or payment.payer_email,
        phone=order_details.payer_phone,
        address=order_details.payer_address,
        city=order_details.payer_city,
        zipcode=order_details.payer_zipcode,

        form_slug=payment.form_slug,
        form_type=payment.form_type,

        items=order_details.items or payment.items,

        custom_fields={**payment.custom_fields, **order_details.custom_fields} if isinstance(order_details.custom_fields, dict) else payment.custom_fields,
        metadata={**payment.metadata, **order_details.metadata} if isinstance(order_details.metadata, dict) else payment.metadata,

        emergency_contact=order_details.emergency_contact
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
                    items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, v))

    return dict(items)


def payment_to_csv_row(payment: AggregatedPayment) -> Dict[str, Any]:
    """Convertit un paiement agrégé en dictionnaire plat pour CSV"""
    row = {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "payment_date": payment.payment_date,
        "payment_amount": payment.payment_amount,
        "payment_state": payment.payment_state,
        "order_date": payment.order_date,
        "order_total_amount": payment.order_total_amount,
        "order_fee_amount": payment.order_fee_amount,
        "order_state": payment.order_state,
        "first_name": payment.first_name,
        "last_name": payment.last_name,
        "email": payment.email,
        "phone": payment.phone or "",
        "address": payment.address or "",
        "city": payment.city or "",
        "zipcode": payment.zipcode or "",
        "form_slug": payment.form_slug,
        "form_type": payment.form_type,
    }

    # Ajouter les items (on prend le premier item comme colonnes principales)
    if payment.items and len(payment.items) > 0:
        first_item = payment.items[0]
        if isinstance(first_item, dict):
            row.update(flatten_dict(first_item, "item_0"))

    # Ajouter les custom fields
    if payment.custom_fields:
        if isinstance(payment.custom_fields, dict):
            row.update(flatten_dict(payment.custom_fields, "custom"))
        elif isinstance(payment.custom_fields, list):
            for i, cf in enumerate(payment.custom_fields):
                if isinstance(cf, dict):
                    row.update(flatten_dict(cf, f"custom_{i}"))

    # Ajouter les metadata
    if payment.metadata:
        row.update(flatten_dict(payment.metadata, "metadata"))

    # Ajouter le contact d'urgence
    if payment.emergency_contact:
        row.update(flatten_dict(payment.emergency_contact, "emergency"))

    return row


def get_csv_headers(payments: List[AggregatedPayment]) -> List[str]:
    """Génère les en-têtes CSV en fonction des données disponibles"""
    all_keys = set()

    for payment in payments:
        row = payment_to_csv_row(payment)
        all_keys.update(row.keys())

    # Trier les clés pour avoir un ordre logique
    ordered_keys = [
        "payment_id", "order_id", "payment_date", "payment_amount", "payment_state",
        "order_date", "order_total_amount", "order_fee_amount", "order_state",
        "first_name", "last_name", "email", "phone", "address", "city", "zipcode",
        "form_slug", "form_type",
    ]

    remaining_keys = sorted(all_keys - set(ordered_keys))

    return ordered_keys + remaining_keys


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
    payments = [parse_payment(p, form_slug) for p in raw_payments]

    # 3. Pour chaque paiement, récupérer les détails de l'ordre
    aggregated_payments = []
    print(f"  Récupération des détails des commandes...")

    for i, payment in enumerate(payments):
        order_id = payment.order_id
        print(f"    [{i+1}/{len(payments)}] Récupération détails commande {order_id}...", end="\r")

        order_details_data = get_order_details(access_token, order_id)

        if order_details_data:
            order_details = parse_order_details(order_details_data)
            aggregated = aggregate_payment(payment, order_details)
            aggregated_payments.append(aggregated)
        else:
            # Si on ne peut pas récupérer les détails, on utilise juste les données du paiement
            # Créer un OrderDetails minimal
            order_details = OrderDetails(
                id=order_id,
                form_slug=form_slug,
                form_type=FORM_CATEGORY,
                date=payment.date,
                amount=payment.amount,
                total_amount=payment.amount,
                fee_amount=0,
                state=payment.state,
                payer_first_name=payment.payer_first_name,
                payer_last_name=payment.payer_last_name,
                payer_email=payment.payer_email
            )
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
            print(f"Erreur lors du traitement de {form_slug}: {e}", file=sys.stderr)

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

