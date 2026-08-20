# Ma Tournée — L'Evasion

Application web légère de planification de tournées pour livraisons scolaires.
Conçue pour ZimaOS (Docker), utilisable depuis plusieurs PC Windows sur le réseau local.

**Dépôt par défaut :** L'Evasion — 24 rue de la République, 57320 Bouzonville  
**Zone carto :** Lorraine + Sarre (département 57 + école française de Sarrebruck)

## Fonctionnalités

- Carnet d'écoles partagé (ajout, modification, suppression, recherche, multi-sélection)
- Import / export CSV compatible Excel (séparateur `;`, UTF-8 BOM)
- Carte interactive (Leaflet), géocodage via Nominatim local
- Tournée optimisée (OSRM local + algorithme 2-opt), tracé, distance et temps
- Cache des coordonnées, mode dégradé si OSRM/Nominatim sont indisponibles
- Auth HTTP Basic optionnelle

## Prérequis

- Docker et Docker Compose sur ZimaOS (ou Linux)
- Espace disque pour les données OSM (Lorraine + Sarre : plusieurs Go)
- RAM recommandée pour la préparation OSRM / import Nominatim : 4 Go ou plus

## Installation rapide

```bash
cd ma-tournee   # dossier du projet
cp .env.example .env

# 1) Préparer les données cartographiques (une seule fois, long)
chmod +x scripts/prepare-osm.sh
./scripts/prepare-osm.sh

# 2) Lancer l'application et les services locaux
docker compose up -d --build
```

Accès local sur le NAS : [http://127.0.0.1:8080](http://127.0.0.1:8080)

## Accès

1. Ouvrez [http://IP-ZIMA:8088](http://IP-ZIMA:8088) (ex. `http://192.168.1.98:8088`)
2. Page de connexion : compte / mot de passe configurés dans `.env` (`AUTH_USER` / `AUTH_PASSWORD`)
3. L’interface est utilisable sur PC et téléphone

Pour désactiver l’auth : laissez `AUTH_USER` et `AUTH_PASSWORD` vides.
## Commandes utiles

```bash
# Construire
docker compose build

# Démarrer
docker compose up -d

# Voir les logs
docker compose logs -f app

# État de santé
curl http://127.0.0.1:8080/health

# Arrêter
docker compose down

# Arrêter sans supprimer les volumes/données disque
docker compose stop
```

## Configuration (`.env`)

| Variable | Rôle |
|---|---|
| `PORT` | Port publié (défaut 8080) |
| `AUTH_USER` / `AUTH_PASSWORD` | Active la page de connexion si les deux sont renseignés |
| `GEOCODER_URL` | Nominatim (défaut service Docker interne) |
| `ROUTER_URL` | OSRM (défaut service Docker interne) |
| `DEPOT_NAME` / `DEPOT_ADDRESS` | Dépôt initial L'Evasion |
| `MAP_CENTER_LAT` / `MAP_CENTER_LON` | Centre carte (Bouzonville) |
| `TILE_URL` | Fond de carte (tuiles OSM par défaut) |
| `AVG_SPEED_KMH` | Vitesse pour estimation si OSRM down |
| `MAX_IMPORT_BYTES` | Taille max d'un import CSV |

Les secrets d'auth ne sont **jamais** exposés au frontend.

## Données persistantes

| Dossier | Contenu |
|---|---|
| `data/` | Base SQLite (écoles, dépôt) — **à sauvegarder en priorité** |
| `osm-data/` | PBF fusionné + fichiers OSRM |
| `nominatim-data/` | Base Nominatim |

### Sauvegarde

```bash
# Stopper brièvement l'écriture (recommandé)
docker compose stop app

# Archive du carnet
tar -czf backup-tournee-$(date +%F).tar.gz data/

docker compose start app
```

### Restauration

```bash
docker compose stop app
tar -xzf backup-tournee-YYYY-MM-DD.tar.gz
docker compose start app
```

### Mise à jour sans perdre les données

```bash
git pull   # ou copiez les nouveaux fichiers du projet
docker compose build app
docker compose up -d
```

Ne supprimez pas les dossiers `data/`, `osm-data/`, `nominatim-data/`.

## Premier import d'écoles

Un fichier d'exemple est fourni : [`examples/ecoles.csv`](examples/ecoles.csv)  
(inclut l'École française de Sarrebruck et Dillingen).

Dans l'interface : **Importer CSV**.

Colonnes attendues : `nom;adresse;telephone;lat;lon`  
(`telephone`, `lat`, `lon` optionnels).

## Architecture

- **app** : FastAPI + SQLite + interface HTML/JS
- **osrm** : calcul d'itinéraires / matrice de distances
- **nominatim** : géocodage d'adresses FR + DE

Si OSRM ou Nominatim sont down, l'application reste utilisable (carnet, coords déjà connues, tournée en distances à vol d'oiseau).

## Tests

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Vérification locale (sans Docker)

Si Docker n'est pas installé sur le PC de développement :

```bash
pip install -r requirements.txt
set DATA_DIR=./data
set GEOCODER_URL=http://127.0.0.1:9
set ROUTER_URL=http://127.0.0.1:9
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Puis ouvrez [http://127.0.0.1:8080](http://127.0.0.1:8080) — `/health` doit répondre avec `"database": true` (géocodeur/routeur en dégradé tant que Nominatim/OSRM ne tournent pas).

Sur ZimaOS, après `./scripts/prepare-osm.sh` et `docker compose up -d --build`, les trois services doivent être up et `/health` passer progressivement à OK.
## Sécurité

- Validation Pydantic des entrées
- Import CSV limité en taille
- Écritures SQLite sérialisées (`BEGIN IMMEDIATE` + verrou)
- Échappement HTML côté interface
- Auth Basic optionnelle sur le LAN

## Limites

- La préparation OSM + le premier import Nominatim sont longs et consomment du disque/RAM
- Les tuiles de fond de carte viennent par défaut d'OpenStreetMap (usage LAN léger) ; marqueurs et tracés fonctionnent même sans tuiles
- Le mode dégradé Haversine ignore le réseau routier
