#!/usr/bin/env bash
# Télécharge Leaflet en local (vendor) pour éviter une dépendance CDN bloquante.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${ROOT_DIR}/app/static/vendor/leaflet"
VERSION="${LEAFLET_VERSION:-1.9.4}"
BASE="https://unpkg.com/leaflet@${VERSION}/dist"
mkdir -p "${DEST}/images"
curl -fsSL -o "${DEST}/leaflet.css" "${BASE}/leaflet.css"
curl -fsSL -o "${DEST}/leaflet.js" "${BASE}/leaflet.js"
curl -fsSL -o "${DEST}/images/marker-icon.png" "${BASE}/images/marker-icon.png"
curl -fsSL -o "${DEST}/images/marker-icon-2x.png" "${BASE}/images/marker-icon-2x.png"
curl -fsSL -o "${DEST}/images/marker-shadow.png" "${BASE}/images/marker-shadow.png"
curl -fsSL -o "${DEST}/images/layers.png" "${BASE}/images/layers.png"
curl -fsSL -o "${DEST}/images/layers-2x.png" "${BASE}/images/layers-2x.png"
# Corrige les chemins d'images dans le CSS vendorisé
sed -i.bak 's|images/|/static/vendor/leaflet/images/|g' "${DEST}/leaflet.css" && rm -f "${DEST}/leaflet.css.bak"
echo "Leaflet ${VERSION} installé dans ${DEST}"
