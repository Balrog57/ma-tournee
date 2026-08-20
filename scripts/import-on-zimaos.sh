#!/bin/bash
set -euo pipefail
# Utilise AUTH_USER / AUTH_PASSWORD de l'environnement (ne pas committer de secrets).
USER_NAME="${AUTH_USER:?Définir AUTH_USER}"
PASS_WORD="${AUTH_PASSWORD:?Définir AUTH_PASSWORD}"
python3 - <<PY
import json
json.dump({"username": "${USER_NAME}", "password": "${PASS_WORD}"}, open("/tmp/login.json", "w"))
PY
rm -f /tmp/mt.cj
curl -s -c /tmp/mt.cj -H 'Content-Type: application/json' --data-binary @/tmp/login.json \
  http://127.0.0.1:8088/api/auth/login
echo
curl -s -b /tmp/mt.cj -o /dev/null -w 'app:%{http_code}\n' http://127.0.0.1:8088/
echo importing...
curl -s -b /tmp/mt.cj -F 'file=@/DATA/AppData/ma-tournee/examples/ecoles_moselle_57.csv' \
  --max-time 300 -o /tmp/import-result.json -w 'import_http:%{http_code}\n' \
  http://127.0.0.1:8088/api/schools/import
cat /tmp/import-result.json
echo
curl -s -b /tmp/mt.cj http://127.0.0.1:8088/api/schools -o /tmp/schools.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/schools.json", encoding="utf-8"))
print("count", len(d))
hits = [x for x in d if "Sarrebr" in x.get("name", "")]
print("sarrebruck", hits[0]["name"] if hits else None, hits[0].get("phone") if hits else None)
PY
