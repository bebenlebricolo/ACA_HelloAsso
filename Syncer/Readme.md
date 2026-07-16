# HelloAsso syncer

Cette collection de scripts Python (3.10+) permet de synchroniser les données collectées par notre club d'aviron via la plateforme HelloAsso et notre stockage de données local et distant (Google Drive ?).

## Prérequis

- Python 3.10+
- Bibliothèque `aiohttp` (installée automatiquement via `requirements.txt`)

Le script est asynchrone (`asyncio` + `aiohttp`) : après l'authentification (étape séquentielle), la récupération des détails de commandes de chaque billetterie est parallélisée, avec une limitation de concurrence configurable.

## Installation

```bash
# Cloner le dépôt ou naviguer dans le dossier Syncer
cd HelloAsso/Syncer

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

### Option 1: Fichier secrets.json
Créer un fichier `secrets.json` dans le dossier Syncer avec vos identifiants HelloAsso :

```json
{
    "clientId": "votre_client_id",
    "clientSecret": "votre_client_secret"
}
```

Un template est fourni : `secrets.template.json`

### Option 2: Variables d'environnement
Vous pouvez aussi utiliser des variables d'environnement :

```bash
export HELLOASSO_CLIENT_ID="votre_client_id"
export HELLOASSO_CLIENT_SECRET="votre_client_secret"
```

> ⚠️ **Ne commitez jamais vos identifiants dans le dépôt git !**
> Ajoutez `secrets.json` à votre `.gitignore`

## Utilisation

### Récupérer les paiements pour une billetterie spécifique

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26
```

### Récupérer les paiements pour plusieurs billetteries

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26
```

### Récupérer toutes les billetteries de type "Membership"

```bash
python Syncer.py --forms all
```

### Spécifier un fichier de configuration personnalisé

```bash
python Syncer.py --config /chemin/vers/mon_secrets.json --forms all
```

### Changer le dossier de sortie

```bash
python Syncer.py --output /chemin/vers/dossier_sortie --forms licence-saison-aviron-sante-25-26
```

### Mode test (dry-run)

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 --dry-run
```

### Parallélisation et throttling

Le script parallélise les requêtes réseau (récupération des détails de commandes, et traitement des billetteries entre elles). Le nombre de requêtes simultanées est borné globalement par un sémaphore.

```bash
# Limiter à 10 requêtes simultanées
python Syncer.py --forms all --concurrency 10

# Espacer davantage les requêtes (throttling) pour éviter d'être signalé (flagged)
python Syncer.py --forms all --concurrency 3 --request-delay 0.5
```

Options disponibles :

- `--concurrency N` : nombre maximum de requêtes HTTP simultanées (défaut : `5`).
- `--request-delay SECONDS` : délai minimum entre requêtes, avec un léger jitter aléatoire (défaut : `0.1`).
- `--max-retries N` : nombre de tentatives en cas d'erreur réseau (défaut : `3`).
- `--retry-delay SECONDS` : délai de base pour le backoff exponentiel des retries (défaut : `2`). Les réponses `429 Too Many Requests` respectent en plus l'en-tête `Retry-After`.

### Mode séquentiel (debug)

Pour déboguer plus facilement (ordre déterministe, une requête à la fois, sans parallélisme) :

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 --sequential
```

### Aide complète

```bash
python Syncer.py --help
```

## Sortie

Le script génère un fichier CSV par billetterie dans le dossier `output/` (par défaut), avec le format :

```
{form_slug}_{timestamp}.csv
```

Chaque fichier contient une ligne par paiement, avec :
- Les informations du paiement (ID, date, montant, état)
- Les informations de l'ordre associé (ID, total, frais)
- Les informations du payeur (nom, prénom, email, téléphone, adresse)
- Les items commandés
- Les champs personnalisés (y compris le contact d'urgence)
- Les métadonnées

## Fonctionnement interne

Le script principal (Syncer.py) :
1. **S'authentifie** auprès des serveurs de HelloAsso et récupère un jeton OAuth (token) via les clé d'API et secrets fournis.
2. **Parcourt les paiements** effectués par les membres sur une série de billetteries en ligne (catégories "Adhésion")
3. **Récupère les informations détaillées** pour chaque paiement (détails de la commande, contact d'urgence, etc.)
4. **Agrège les données** (SQL JOIN logiciel) entre les paiements et leurs détails
5. **Génère des fichiers CSV** avec toutes les informations consolidées (un fichier par billeterie)

## Personnalisation

Vous pouvez modifier les constantes suivantes dans `Syncer.py` (valeurs par défaut, surchargeables en ligne de commande) :

- `ORGANIZATION_SLUG` : Le slug de votre organisation HelloAsso
- `FORM_CATEGORY` : Le type de formulaire à traiter (par défaut : "Membership")
- `DEFAULT_CONCURRENCY` : Nombre de requêtes simultanées par défaut (option `--concurrency`)
- `REQUEST_DELAY` : Délai entre les requêtes API (option `--request-delay`, pour éviter le rate limiting)
- `MAX_RETRIES` : Nombre de tentatives en cas d'erreur réseau (option `--max-retries`)
- `RETRY_DELAY` : Délai de base pour le backoff des retries (option `--retry-delay`)

## Structure des données

### Exemple de données récupérées

Les paiements sont structurés avec :
- **Données de paiement** : ID, date, montant, état, informations du payeur
- **Données de commande** : ID, date, montant total, frais, état
- **Items** : Liste des articles commandés
- **Champs personnalisés** : Inclut le contact d'urgence si présent
- **Métadonnées** : Données supplémentaires

Le CSV généré aplatit toutes ces informations en colonnes.

## Dépannage

### Erreur d'authentification
Vérifiez que :
- Vos identifiants sont corrects
- Le fichier `secrets.json` est dans le bon dossier ou que les variables d'environnement sont définies

### Aucune donnée récupérée
Vérifiez que :
- Le slug de la billetterie est correct (en kebab-case)
- L'organisation a bien des paiements pour cette billetterie
- Vous avez les droits d'accès à l'API

### Problèmes de rate limiting
Réduisez la concurrence et espacez les requêtes :

```bash
python Syncer.py --forms all --concurrency 2 --request-delay 1.0
```

Vous pouvez aussi passer en mode séquentiel (`--sequential`) pour éliminer complètement le parallélisme. Le script respecte automatiquement l'en-tête `Retry-After` sur les réponses `429`.

## Contribution

Les contributions sont bienvenues ! Ouvrez une issue ou soumettez une pull request.

## License

Ce projet est sous licence MIT (ou à définir selon vos besoins).

# Comment l'utiliser ?
Cet outil a besoin d'un seul fichier de configuration: `secrets.json`.
Il suffit, lors de la premiere execution, de copier le fichier [secrets.template.json](secrets.template.json) et de l'éditer.

Exemple de fichier `secrets.json`:
```json
{
    "clientId" : "<identifiant généré depuis le portail admin de HelloAsso>",
    "clientSecret" : "<secret généré depuis le portail admin de HelloAsso>"
}
```

Puis:
```bash
python Syncer.py