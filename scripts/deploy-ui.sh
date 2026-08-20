#!/bin/bash
set -e
export DOCKER_CONFIG=/tmp/docker-empty
mkdir -p /tmp/docker-empty
echo '{}' > /tmp/docker-empty/config.json
cd /DATA/AppData/ma-tournee
docker build -t 127.0.0.1:5500/ma-tournee:latest .
docker push 127.0.0.1:5500/ma-tournee:latest
docker compose -f docker-compose.casaos.yml up -d --force-recreate --pull always
sleep 6
docker ps --filter name=matournee --format '{{.Names}} {{.Status}}'
curl -s http://127.0.0.1:8088/health
echo
docker exec matournee-app grep -c focusDepot /app/app/static/js/map.js
docker exec matournee-app grep -c list-controls /app/app/static/index.html
docker exec matournee-app grep -c btn-copy-phone /app/app/static/index.html
docker exec matournee-app grep -c depot-summary /app/app/static/index.html
docker exec matournee-app grep -c school-marker-star /app/app/static/css/app.css
