#!/usr/bin/env python3
"""Inject CasaOS icon into installed ma-tournee compose (run as root via docker)."""
from pathlib import Path

path = Path("/compose.yml")
text = path.read_text(encoding="utf-8")
icon_line = '    icon: http://192.168.1.98:8088/static/img/logo-ma-tournee.png\n'
if "icon:" in text and "logo-ma-tournee" in text:
    print("icon already present")
else:
    # remove any stale icon lines under x-casaos
    lines = []
    for line in text.splitlines(True):
        if line.strip().startswith("icon:"):
            continue
        lines.append(line)
    text = "".join(lines)
    marker = "x-casaos:\n"
    if marker not in text:
        raise SystemExit("x-casaos block missing")
    # insert icon after hostname if present, else right after x-casaos
    if "    hostname:" in text:
        out = []
        inserted = False
        for line in text.splitlines(True):
            out.append(line)
            if (not inserted) and line.startswith("    hostname:"):
                out.append(icon_line)
                inserted = True
        text = "".join(out)
    else:
        text = text.replace(marker, marker + icon_line, 1)
    # also tip/description optional
    path.write_text(text, encoding="utf-8")
    print("icon injected")

print("--- x-casaos ---")
in_block = False
for line in path.read_text(encoding="utf-8").splitlines():
    if line.startswith("x-casaos:"):
        in_block = True
    if in_block:
        print(line)
