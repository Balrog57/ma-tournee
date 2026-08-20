from __future__ import annotations

import re


_POSTAL_CITY = re.compile(
    r"^(?:F-?)?(?P<postal>\d{4,5})\s+(?P<city>.+)$",
    re.IGNORECASE,
)
_DE_POSTAL_CITY = re.compile(
    r"^(?P<postal>\d{5})\s+(?P<city>.+)$",
)


def extract_city(address: str) -> str:
    """Extrait une ville approximative depuis une adresse complète."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return ""

    # Dernier segment utile (ignore "Allemagne" / "France" seuls)
    for candidate in reversed(parts):
        low = candidate.lower()
        if low in {"france", "allemagne", "germany", "deutschland"}:
            continue
        m = _POSTAL_CITY.match(candidate) or _DE_POSTAL_CITY.match(candidate)
        if m:
            city = m.group("city").strip()
            # Enlever éventuel pays collé
            city = re.sub(r"\s+(France|Allemagne|Germany)$", "", city, flags=re.I).strip()
            return city
        # Pas de code postal : si le segment n'est pas qu'une rue, le prendre
        if not re.search(r"\b(rue|avenue|allée|allee|place|impasse|chemin|route|straße|strasse|str\.)\b", candidate, re.I):
            return candidate
    # Repli : dernier segment
    return parts[-1]
