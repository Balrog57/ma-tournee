#!/usr/bin/env bash
# Prépare l'extract OSM Lorraine + Sarre pour OSRM et Nominatim.
# À exécuter sur la machine hôte (ZimaOS / Linux) avant le premier docker compose up.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OSM_DIR="${ROOT_DIR}/osm-data"
mkdir -p "${OSM_DIR}"

LORRAINE_URL="${OSM_LORRAINE_URL:-https://download.geofabrik.de/europe/france/lorraine-latest.osm.pbf}"
SAARLAND_URL="${OSM_SAARLAND_URL:-https://download.geofabrik.de/europe/germany/saarland-latest.osm.pbf}"

LORRAINE_PBF="${OSM_DIR}/lorraine-latest.osm.pbf"
SAARLAND_PBF="${OSM_DIR}/saarland-latest.osm.pbf"
MERGED_PBF="${OSM_DIR}/region.osm.pbf"
OSRM_IMG="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v5.27.1}"

echo "==> Téléchargement Lorraine"
if [[ ! -f "${LORRAINE_PBF}" ]]; then
  curl -L --fail -o "${LORRAINE_PBF}" "${LORRAINE_URL}"
else
  echo "    déjà présent: ${LORRAINE_PBF}"
fi

echo "==> Téléchargement Sarre (Saarland)"
if [[ ! -f "${SAARLAND_PBF}" ]]; then
  curl -L --fail -o "${SAARLAND_PBF}" "${SAARLAND_URL}"
else
  echo "    déjà présent: ${SAARLAND_PBF}"
fi

echo "==> Fusion des PBF (osmium via Docker)"
docker run --rm -v "${OSM_DIR}:/data" iboates/osmium:latest \
  osmium merge \
    /data/lorraine-latest.osm.pbf \
    /data/saarland-latest.osm.pbf \
    -o /data/region.osm.pbf \
    --overwrite

echo "==> Préparation OSRM (extract / partition / customize)"
# Nettoyage anciens fichiers osrm (conserve les pbf)
find "${OSM_DIR}" -maxdepth 1 -type f -name 'region.osrm*' -delete || true

docker run --rm -v "${OSM_DIR}:/data" "${OSRM_IMG}" \
  osrm-extract -p /opt/car.lua /data/region.osm.pbf

docker run --rm -v "${OSM_DIR}:/data" "${OSRM_IMG}" \
  osrm-partition /data/region.osrm

docker run --rm -v "${OSM_DIR}:/data" "${OSRM_IMG}" \
  osrm-customize /data/region.osrm

echo ""
echo "Préparation terminée."
echo "Fichiers:"
echo "  - ${MERGED_PBF}  (Nominatim)"
echo "  - ${OSM_DIR}/region.osrm*  (OSRM)"
echo ""
echo "Lancez ensuite: docker compose up -d"
echo "Le premier démarrage de Nominatim importe le PBF (peut prendre longtemps)."
