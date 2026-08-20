#!/usr/bin/env python3
"""Exporte les écoles ouvertes du département 57 (Moselle) depuis l'annuaire Éducation nationale."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import httpx

API = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education/records"
# « École » = premier degré (maternelle / élémentaire / primaire). Source officielle à jour.
WHERE = 'code_departement="057" AND etat="OUVERT" AND type_etablissement="Ecole"'
PAGE = 100


def fetch_all() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    with httpx.Client(timeout=60.0) as client:
        while True:
            response = client.get(
                API,
                params={
                    "where": WHERE,
                    "limit": PAGE,
                    "offset": offset,
                    "order_by": "nom_commune,nom_etablissement",
                    "select": (
                        "nom_etablissement,adresse_1,adresse_2,adresse_3,code_postal,"
                        "nom_commune,telephone,latitude,longitude,statut_public_prive,"
                        "ecole_maternelle,ecole_elementaire"
                    ),
                },
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("results") or []
            rows.extend(batch)
            total = int(payload.get("total_count") or 0)
            offset += len(batch)
            print(f"… {offset}/{total}", file=sys.stderr)
            if not batch or offset >= total:
                break
    return rows


def build_address(row: dict) -> str:
    parts = []
    for key in ("adresse_1", "adresse_2"):
        value = (row.get(key) or "").strip()
        if value:
            parts.append(value)
    cp = (row.get("code_postal") or "").strip()
    city = (row.get("nom_commune") or "").strip()
    # adresse_3 often already contains "CP VILLE"
    a3 = (row.get("adresse_3") or "").strip()
    if a3 and a3.lower() not in " ".join(parts).lower():
        if cp and city and a3.replace(" ", "").endswith((cp + city).replace(" ", "")):
            pass
        elif not (cp or city):
            parts.append(a3)
    line = ", ".join(parts)
    if cp or city:
        line = f"{line}, {cp} {city}".strip(", ").replace("  ", " ")
    return line


def format_phone(raw: object) -> str:
    if raw is None:
        return ""
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) == 10:
        return " ".join(digits[i : i + 2] for i in range(0, 10, 2))
    return str(raw).strip()


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "examples" / "ecoles_moselle_57.csv"
    rows = fetch_all()
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(["nom", "adresse", "telephone", "lat", "lon"])
        for row in rows:
            name = (row.get("nom_etablissement") or "").strip()
            address = build_address(row)
            if not name or not address:
                continue
            lat = row.get("latitude")
            lon = row.get("longitude")
            writer.writerow(
                [
                    name,
                    address,
                    format_phone(row.get("telephone")),
                    "" if lat is None else lat,
                    "" if lon is None else lon,
                ]
            )
        # École franco-allemande hors 57 (Sarrebruck)
        writer.writerow(
            [
                "École française de Sarrebruck et Dillingen",
                "Halbergstraße 112, 66121 Saarbrücken, Allemagne",
                "0049 681 62 62 4",
                49.2228,
                7.0075,
            ]
        )
    print(f"Écrit {out} ({len(rows)} écoles 57 + Sarrebruck)", file=sys.stderr)


if __name__ == "__main__":
    main()
