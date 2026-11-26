#!/usr/bin/env python3
"""Pruebas de las notas agregadas para releases estables."""

import importlib.util
import tempfile
from pathlib import Path

path = Path(__file__).with_name("release-notes.py")
spec = importlib.util.spec_from_file_location("release_notes", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as directory:
    changelog = Path(directory) / "CHANGELOG.md"
    changelog.write_text(
        "# Cambios\n\n"
        "## 1.4.5\n\n- Base estable.\n\n"
        "## 1.4.6\n\n- Actualización segura.\n\n"
        "## 1.4.7\n\n- GRUB validado.\n\n"
        "## 1.4.8\n\n- Salud seguro.\n\n"
        "## 1.4.9\n\n- Índices frescos.\n",
        encoding="utf-8",
    )
    notes = module.render(changelog, "v1.4.5", "1.4.9")
    assert "Base estable" not in notes
    assert "## 1.4.6" in notes and "Actualización segura" in notes
    assert "## 1.4.7" in notes and "GRUB validado" in notes
    assert "## 1.4.8" in notes and "Salud seguro" in notes
    assert "## 1.4.9" in notes and "Índices frescos" in notes

    notes = module.render(changelog, "v1.4.8", "1.4.9")
    assert "## 1.4.9" in notes
    assert "GRUB validado" not in notes and "Salud seguro" not in notes

    notes = module.render(changelog, "", "1.4.7")
    assert "## 1.4.5" in notes
    assert "## 1.4.7" in notes
    assert "Salud seguro" not in notes

print("✔ Notas de release: agregan versiones intermedias y excluyen la base anterior")
