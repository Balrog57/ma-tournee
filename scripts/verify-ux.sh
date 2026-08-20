#!/bin/bash
set -e
export DOCKER_CONFIG=/tmp/docker-empty
curl -s -c /tmp/mt.cj -H 'Content-Type: application/json' \
  -d '{"username":"evasion","password":"evasion"}' \
  http://127.0.0.1:8088/api/auth/login >/dev/null
curl -s -b /tmp/mt.cj http://127.0.0.1:8088/api/schools > /tmp/schools.json
python3 <<'PY'
import json
d = json.load(open("/tmp/schools.json"))
print("count", len(d))
print("sample", {k: d[0].get(k) for k in ("id", "name", "city", "favorite")})
print("has_city", sum(1 for s in d if s.get("city")))
open("/tmp/sid.txt", "w").write(str(d[0]["id"]))
PY
ID=$(cat /tmp/sid.txt)
curl -s -b /tmp/mt.cj -X PUT -H 'Content-Type: application/json' \
  -d '{"favorite":true}' "http://127.0.0.1:8088/api/schools/$ID" > /tmp/fav.json
python3 <<'PY'
import json
d = json.load(open("/tmp/fav.json"))
print("fav_ok", d.get("favorite"), d.get("city"), (d.get("name") or "")[:50])
PY
curl -s -b /tmp/mt.cj -X PUT -H 'Content-Type: application/json' \
  -d '{"favorite":false}' "http://127.0.0.1:8088/api/schools/$ID" >/dev/null
docker exec matournee-app grep -c selectSchoolFromMap /app/app/static/js/app.js
docker exec matournee-app grep -c favorites-header /app/app/static/js/app.js
docker exec matournee-app grep -c 'Localiser sur la carte' /app/app/static/index.html
docker ps --filter name=matournee --format '{{.Names}} {{.Status}}'
