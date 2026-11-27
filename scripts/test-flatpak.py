#!/usr/bin/env python3
"""Test Flatpak manifest and metadata for AiO Debian GUI."""
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


def test_manifest_exists():
    """Test that the Flatpak manifest exists."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    assert manifest.exists(), f"Manifest not found: {manifest}"
    print("✓ Manifest exists")


def test_manifest_valid_yaml():
    """Test that the manifest is valid YAML."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)
    assert data is not None, "Manifest is empty"
    assert "app-id" in data, "Missing app-id"
    assert data["app-id"] == "io.github.julioayusoalende_hue.aio_debian_gui"
    print("✓ Manifest is valid YAML with correct app-id")


def test_architecture_support():
    """Test that the manifest supports x86_64 and aarch64."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)

    # Check modules have only-arches for x86_64 and aarch64
    for module in data.get("modules", []):
        arches = module.get("only-arches", [])
        if arches:
            assert "x86_64" in arches, f"Module {module.get('name')} missing x86_64"
            assert "aarch64" in arches, f"Module {module.get('name')} missing aarch64"
    print("✓ Architecture support: x86_64 and aarch64")


def test_grub_tools_included():
    """Test that grub-script-check and related tools are included."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)

    # Check for host-tools module with grub tools
    host_tools = None
    for module in data.get("modules", []):
        if module.get("name") == "host-tools":
            host_tools = module
            break

    assert host_tools is not None, "Missing host-tools module"
    commands = host_tools.get("build-commands", [])
    grub_tools = ["grub-script-check", "grub-mkconfig", "update-grub", "os-prober"]
    for tool in grub_tools:
        found = any(tool in cmd for cmd in commands)
        assert found, f"Missing {tool} in host-tools build-commands"
    print("✓ GRUB tools included: grub-script-check, grub-mkconfig, update-grub, os-prober")


def test_finish_args_grub_access():
    """Test that finish-args include GRUB filesystem access."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)

    finish_args = data.get("finish-args", [])
    grub_paths = [
        "host/etc/default:rw",
        "host/boot/grub:rw",
        "host/usr/sbin/grub-mkconfig:x",
        "host/usr/bin/grub-script-check:x",
        "host/usr/sbin/update-grub:x",
    ]
    for path in grub_paths:
        found = any(path in arg for arg in finish_args)
        assert found, f"Missing GRUB path in finish-args: {path}"
    print("✓ GRUB filesystem access configured in finish-args")


def test_flatpak_id_env():
    """Test that FLATPAK_ID environment variable is set."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)

    finish_args = data.get("finish-args", [])
    found = any("FLATPAK_ID=io.github.julioayusoalende_hue.aio_debian_gui" in arg for arg in finish_args)
    assert found, "FLATPAK_ID not set in finish-args"
    print("✓ FLATPAK_ID environment variable configured")


def test_metainfo_exists():
    """Test that metainfo.xml exists and is valid."""
    metainfo = Path(__file__).resolve().parents[1] / "package/usr/share/metainfo/io.github.julioayusoalende_hue.aio_debian_gui.metainfo.xml"
    assert metainfo.exists(), f"Metainfo not found: {metainfo}"

    tree = ET.parse(metainfo)
    root = tree.getroot()
    assert root.tag == "component"
    assert root.get("type") == "desktop-application"
    identificador = root.find("id")
    assert identificador is not None and identificador.text == "io.github.julioayusoalende_hue.aio_debian_gui"

    # Las entradas <releases> las genera scripts/build-deb.sh al empaquetar;
    # el metainfo del repositorio no debe llevar versiones estáticas.
    assert root.find("releases") is None, "Static releases section must be generated at build time"
    print("✓ Metainfo.xml valid (releases generated at build time)")


def test_desktop_file_exists():
    """Test that desktop file exists and has correct MIME types."""
    desktop = Path(__file__).resolve().parents[1] / "package/usr/share/applications/aio-debian-gui.desktop"
    assert desktop.exists(), f"Desktop file not found: {desktop}"

    content = desktop.read_text()
    assert "MimeType=application/vnd.debian.binary-package;application/x-deb;application/vnd.flatpak.ref;" in content
    print("✓ Desktop file has correct MIME types")


def test_icons_exist():
    """Test that all required icon sizes exist."""
    icon_sizes = [48, 64, 128, 256, 512]
    for size in icon_sizes:
        icon = Path(__file__).resolve().parents[1] / f"package/usr/share/icons/hicolor/{size}x{size}/apps/aio-debian-gui.png"
        assert icon.exists(), f"Missing icon: {icon}"
    print("✓ All icon sizes present")


def test_polkit_policy_exists():
    """Test that polkit policy file exists."""
    policy = Path(__file__).resolve().parents[1] / "package/usr/share/polkit-1/actions/es.aiodebian.gui.policy"
    assert policy.exists(), f"Polkit policy not found: {policy}"
    content = policy.read_text()
    assert "es.aiodebian.gui.mantenimiento" in content
    print("✓ Polkit policy exists")


def test_helper_scripts_exist():
    """Test that all helper scripts exist."""
    helpers = [
        "aio-debian-gui-helper",
        "aio-grub-settings",
        "aio-apt-sources-backup",
        "aio-clock-enable",
    ]
    base = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui"
    for helper in helpers:
        path = base / helper
        assert path.exists(), f"Missing helper: {path}"
        assert os.access(path, os.X_OK), f"Helper not executable: {path}"
    print("✓ All helper scripts present and executable")


def test_core_modules_exist():
    """Test that all core Python modules exist."""
    core_dir = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio_core"
    required_modules = [
        "__init__.py",
        "clock.py",
        "desktop_backup.py",
        "diagnostics.py",
        "history.py",
        "host_integration.py",
        "preferences.py",
        "preflight.py",
        "recommended_list.py",
        "scheduler.py",
        "updates.py",
        "constants.py",
        "fastfetch.py",
        "gtk_appearance.py",
        "gtk_scheduler.py",
        "operations.py",
        "translations.py",
        "extensions.py",
        "health.py",
        "health_dashboard.py",
        "host_repository.py",
        "firmware.py",
        "gnome_extensions.py",
        "appearance.py",
        "nvidia.py",
    ]
    for module in required_modules:
        path = core_dir / module
        assert path.exists(), f"Missing core module: {module}"
    print("✓ All core modules present")





def test_recommended_icons_exist():
    """Test that recommended app icons exist."""
    icon_dir = Path(__file__).resolve().parents[1] / "package/usr/share/aio-debian-gui/recommended-icons"
    assert icon_dir.exists(), "Recommended icons directory missing"
    icons = list(icon_dir.glob("*.png")) + list(icon_dir.glob("*.svg"))
    assert len(icons) > 20, f"Expected >20 recommended icons, found {len(icons)}"
    print(f"✓ Recommended icons present ({len(icons)} icons)")


def test_backup_icons_exist():
    """Test that backup icons exist."""
    icon_dir = Path(__file__).resolve().parents[1] / "package/usr/share/aio-debian-gui/backup-icons"
    assert icon_dir.exists(), "Backup icons directory missing"
    icons = list(icon_dir.glob("*.png"))
    assert len(icons) > 0, "No backup icons found"
    print(f"✓ Backup icons present ({len(icons)} icons)")


def test_version_consistency():
    """Test that version is consistent across files."""
    # La versión del paquete (sin época) es la referencia; el metainfo no
    # lleva <releases> estático porque lo genera scripts/build-deb.sh.
    control = Path(__file__).resolve().parents[1] / "package/DEBIAN/control"
    paquete_version = None
    for linea in control.read_text().splitlines():
        if linea.startswith("Version:"):
            paquete_version = linea.split(":", 1)[1].strip().split(":", 1)[-1]
            break

    # Read version from main script
    main_script = Path(__file__).resolve().parents[1] / "package/usr/bin/aio-debian-gui"
    content = main_script.read_text()
    import re
    match = re.search(r'AIO_DEBIAN_GUI_VERSION = "([^"]+)"', content)
    script_version = match.group(1) if match else None

    # Read version from helper
    helper = Path(__file__).resolve().parents[1] / "package/usr/lib/aio-debian-gui/aio-debian-gui-helper"
    content = helper.read_text()
    match = re.search(r'HELPER_VERSION=([^\n]+)', content)
    helper_version = match.group(1) if match else None

    assert paquete_version == script_version == helper_version, \
        f"Version mismatch: control={paquete_version}, script={script_version}, helper={helper_version}"
    print(f"✓ Version consistent across files: {paquete_version}")


def test_flatpak_manifest_schema():
    """Validate manifest against expected schema."""
    manifest = Path(__file__).resolve().parents[1] / "io.github.julioayusoalende_hue.aio_debian_gui.yml"
    with open(manifest) as f:
        data = yaml.safe_load(f)

    # Required fields
    required = ["app-id", "runtime", "runtime-version", "sdk", "command", "finish-args", "modules"]
    for field in required:
        assert field in data, f"Missing required field: {field}"

    # Check runtime is GNOME
    assert data["runtime"] == "org.gnome.Platform"
    assert data["sdk"] == "org.gnome.Sdk"
    assert data["runtime-version"] == "47"
    assert data["command"] == "aio-debian-gui"

    print("✓ Manifest schema valid")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_manifest_exists,
        test_manifest_valid_yaml,
        test_architecture_support,
        test_grub_tools_included,
        test_finish_args_grub_access,
        test_flatpak_id_env,
        test_metainfo_exists,
        test_desktop_file_exists,
        test_icons_exist,
        test_polkit_policy_exists,
        test_helper_scripts_exist,
        test_core_modules_exist,
        test_recommended_icons_exist,
        test_backup_icons_exist,
        test_version_consistency,
        test_flatpak_manifest_schema,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
