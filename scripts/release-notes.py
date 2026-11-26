#!/usr/bin/env python3
"""Genera notas de release estables acumulando versiones intermedias."""

import re
import subprocess
import sys
from pathlib import Path

HEADING = re.compile(r"^## ([0-9]+\.[0-9]+\.[0-9]+)\s*$")


def sections(path):
    content = Path(path).read_text(encoding="utf-8")
    found = []
    current_version = None
    current_lines = []
    for line in content.splitlines():
        match = HEADING.match(line)
        if match:
            if current_version is not None:
                found.append((current_version, current_lines))
            current_version = match.group(1)
            current_lines = []
        elif current_version is not None:
            current_lines.append(line)
    if current_version is not None:
        found.append((current_version, current_lines))
    return found


def newer(version, previous):
    return subprocess.run(
        ["dpkg", "--compare-versions", version, "gt", previous],
        check=False,
    ).returncode == 0


def render(path, previous_tag, current_version):
    previous = previous_tag.lstrip("v") if previous_tag else None
    selected = []
    for version, lines in sections(path):
        if newer(version, current_version):
            continue
        if previous and not newer(version, previous):
            continue
        body = "\n".join(lines).strip()
        if body:
            selected.append((version, body))
    if not selected:
        raise ValueError("No hay secciones de changelog para la release.")
    preamble = f"Cambios desde {previous}:\n\n" if previous else "Cambios:\n\n"
    return preamble + "\n\n".join(f"## {version}\n{body}" for version, body in selected) + "\n"


def main(argv):
    if len(argv) != 4:
        raise SystemExit("Uso: release-notes.py CHANGELOG [TAG_ANTERIOR] VERSION_ACTUAL")
    print(render(argv[1], argv[2], argv[3]), end="")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
