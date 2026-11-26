#!/usr/bin/env python3
"""
Calamares module: AyusOS AIO Setup (Python job module)

Post-install configuration that writes /etc/ayusos/ayusos.conf
with the user's preselected options, before first boot.
Uses the libcalamares Python API.
"""

import os
import subprocess
from pathlib import Path

import libcalamares
from libcalamares.utils import debug


def _write_ayusos_config(config, target_root):
    """Escribe /etc/ayusos/ayusos.conf (TOML) en el sistema instalado."""
    config_path = Path(target_root) / "etc" / "ayusos" / "ayusos.conf"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Configuracion de AyusOS generada por Calamares", ""]
    for section, values in config.items():
        lines.append("[%s]" % section)
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append("%s = %s" % (key, str(value).lower()))
            elif isinstance(value, list):
                items = ", ".join('"%s"' % v for v in value)
                lines.append("%s = [%s]" % (key, items))
            elif isinstance(value, str):
                lines.append('%s = "%s"' % (key, value))
            else:
                lines.append("%s = %s" % (key, value))
        lines.append("")

    config_path.write_text("\n".join(lines), encoding="utf-8")
    debug("ayusos-aio-setup: escrito %s" % config_path)
    return True


def _build_config(job):
    """Construye el diccionario de configuracion desde job.configuration."""
    c = job.configuration or {}
    return {
        "repos": {
            "contrib_nonfree": bool(c.get("enableContribNonFree", True)),
            "backports": bool(c.get("enableBackports", True)),
            "backports_mesa": bool(c.get("enableBackportsMesa", True)),
        },
        "flatpak": {
            "enabled": bool(c.get("enableFlatpak", True)),
            "flathub": bool(c.get("enableFlathub", True)),
            "extra_remotes": [],
        },
        "kernel": {"variant": c.get("kernelVariant", "stable")},
        "nvidia": {
            "mode": c.get("nvidiaMode", "auto"),
            "prime_offload": bool(c.get("nvidiaPrime", True)),
        },
        "maintenance": {
            "schedule": c.get("maintenanceSchedule", "weekly"),
            "time": c.get("maintenanceTime", "03:00"),
            "tasks": c.get("maintenanceTasks", [
                "upgrade", "autoclean", "flatpak-update", "snap-update",
                "clean-journal", "rebootcheck"]),
            "notify": bool(c.get("maintenanceNotify", True)),
        },
        "apps": {
            "profile": c.get("appsProfile", "minimal"),
            "auto_install": bool(c.get("autoInstallApps", True)),
        },
        "gnome_extensions": {
            "enabled_by_default": c.get("gnomeExtensions", [
                "gnome-ext-appindicator", "gnome-ext-blur-shell",
                "gnome-ext-dash-to-dock"]),
        },
        "appearance": {
            "theme": c.get("theme", "system"),
            "accent": c.get("accent", "ayusos"),
            "wallpaper_mode": c.get("wallpaperMode", "auto"),
        },
        "snapshots": {
            "btrfs_enabled": bool(c.get("btrfsSnapshots", True)),
            "timeshift_enabled": bool(c.get("timeshiftSnapshots", True)),
            "grub_btrfs": bool(c.get("grubBtrfs", True)),
            "schedule": c.get("snapshotSchedule", "daily"),
            "retention": c.get("snapshotRetention", "7d"),
        },
        "onboarding": {"completed": False, "version": "0.0.0"},
    }


def run():
    """Punto de entrada del modulo Calamares.

    Devuelve None en exito, o (mensaje, detalle) en fallo.
    """
    root = libcalamares.globalstorage.value("rootMountPoint")
    if not root:
        return ("AyusOS setup", "No se encontro rootMountPoint en globalstorage")

    debug("ayusos-aio-setup: rootMountPoint=%s" % root)

    try:
        config = _build_config(libcalamares.job)
        _write_ayusos_config(config, root)

        # Marcador de preset aplicado (el onboarding grafico solo confirma)
        marker = Path(root) / "var" / "lib" / "ayusos" / "calamares-preset-applied"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("1", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return ("AyusOS setup", "Error escribiendo configuracion: %s" % exc)

    debug("ayusos-aio-setup: configuracion base aplicada")
    return None