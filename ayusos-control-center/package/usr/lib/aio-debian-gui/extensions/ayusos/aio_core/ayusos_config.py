"""Configuración unificada de AyusOS: /etc/ayusos/ayusos.conf + preferencias usuario.

Esquema TOML tipado con validación, migración y fusión de prioridades:
  defaults código < /etc/ayusos/ayusos.conf < ~/.config/aio-debian-gui/preferences.json
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11


# Rutas
SYSTEM_CONFIG_PATH = Path("/etc/ayusos/ayusos.conf")
USER_CONFIG_DIR = Path.home() / ".config" / "aio-debian-gui"
USER_PREFS_PATH = USER_CONFIG_DIR / "preferences.json"
MARKER_ONBOARDING_DONE = Path("/var/lib/ayusos/onboarding-done")


# Valores por defecto del sistema (código)
SYSTEM_DEFAULTS = {
    "repos": {
        "contrib_nonfree": True,
        "backports": True,
        "backports_mesa": True,
    },
    "flatpak": {
        "enabled": True,
        "flathub": True,
        "extra_remotes": [],
    },
    "kernel": {
        "variant": "stable",  # stable, backports, hwe
    },
    "nvidia": {
        "mode": "auto",  # auto, manual, none
        "prime_offload": True,
    },
    "maintenance": {
        "schedule": "weekly",  # daily, weekly, monthly, disabled
        "time": "03:00",
        "tasks": [
            "upgrade",
            "autoclean",
            "flatpak-update",
            "snap-update",
            "rebootcheck",
        ],
        "notify": True,
    },
    "apps": {
        "profile": "minimal",  # minimal, development, multimedia, gaming, full
        "auto_install": False,
    },
    "gnome_extensions": {
        "enabled_by_default": [
            "gnome-ext-appindicator",
            "gnome-ext-blur-shell",
            "gnome-ext-dash-to-dock",
        ],
    },
    "appearance": {
        "theme": "system",  # system, light, dark
        "accent": "ayusos",
        "wallpaper_mode": "auto",  # auto, light, dark, custom
    },
    "snapshots": {
        "btrfs_enabled": True,
        "timeshift_enabled": True,
        "grub_btrfs": True,
        "schedule": "daily",
        "retention": "7d",
    },
    "onboarding": {
        "completed": False,
        "version": "0.0.0",
    },
}


@dataclass
class ReposConfig:
    contrib_nonfree: bool = True
    backports: bool = True
    backports_mesa: bool = True


@dataclass
class FlatpakConfig:
    enabled: bool = True
    flathub: bool = True
    extra_remotes: list[str] = field(default_factory=list)


@dataclass
class KernelConfig:
    variant: str = "stable"  # stable, backports, hwe


@dataclass
class NvidiaConfig:
    mode: str = "auto"  # auto, manual, none
    prime_offload: bool = True


@dataclass
class MaintenanceConfig:
    schedule: str = "weekly"  # daily, weekly, monthly, disabled
    time: str = "03:00"
    tasks: list[str] = field(default_factory=lambda: [
        "upgrade", "autoclean", "flatpak-update", "snap-update",
        "rebootcheck"
    ])
    notify: bool = True


@dataclass
class AppsConfig:
    profile: str = "minimal"  # minimal, development, multimedia, gaming, full
    auto_install: bool = False


@dataclass
class GnomeExtensionsConfig:
    enabled_by_default: list[str] = field(default_factory=lambda: [
        "gnome-ext-appindicator",
        "gnome-ext-blur-shell",
        "gnome-ext-dash-to-dock",
    ])


@dataclass
class AppearanceConfig:
    theme: str = "system"  # system, light, dark
    accent: str = "ayusos"
    wallpaper_mode: str = "auto"  # auto, light, dark, custom


@dataclass
class SnapshotsConfig:
    btrfs_enabled: bool = True
    timeshift_enabled: bool = True
    grub_btrfs: bool = True
    schedule: str = "daily"
    retention: str = "7d"


@dataclass
class OnboardingConfig:
    completed: bool = False
    version: str = "0.0.0"


@dataclass
class AyusOSConfig:
    repos: ReposConfig = field(default_factory=ReposConfig)
    flatpak: FlatpakConfig = field(default_factory=FlatpakConfig)
    kernel: KernelConfig = field(default_factory=KernelConfig)
    nvidia: NvidiaConfig = field(default_factory=NvidiaConfig)
    maintenance: MaintenanceConfig = field(default_factory=MaintenanceConfig)
    apps: AppsConfig = field(default_factory=AppsConfig)
    gnome_extensions: GnomeExtensionsConfig = field(default_factory=GnomeExtensionsConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    snapshots: SnapshotsConfig = field(default_factory=SnapshotsConfig)
    onboarding: OnboardingConfig = field(default_factory=OnboardingConfig)

    # Versión del esquema para migraciones
    SCHEMA_VERSION = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos": asdict(self.repos),
            "flatpak": asdict(self.flatpak),
            "kernel": asdict(self.kernel),
            "nvidia": asdict(self.nvidia),
            "maintenance": asdict(self.maintenance),
            "apps": asdict(self.apps),
            "gnome_extensions": asdict(self.gnome_extensions),
            "appearance": asdict(self.appearance),
            "snapshots": asdict(self.snapshots),
            "onboarding": asdict(self.onboarding),
            "_schema_version": self.SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AyusOSConfig":
        return cls(
            repos=ReposConfig(**data.get("repos", {})),
            flatpak=FlatpakConfig(**data.get("flatpak", {})),
            kernel=KernelConfig(**data.get("kernel", {})),
            nvidia=NvidiaConfig(**data.get("nvidia", {})),
            maintenance=MaintenanceConfig(**data.get("maintenance", {})),
            apps=AppsConfig(**data.get("apps", {})),
            gnome_extensions=GnomeExtensionsConfig(**data.get("gnome_extensions", {})),
            appearance=AppearanceConfig(**data.get("appearance", {})),
            snapshots=SnapshotsConfig(**data.get("snapshots", {})),
            onboarding=OnboardingConfig(**data.get("onboarding", {})),
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Fusiona recursivamente override sobre base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_toml(path: Path) -> dict[str, Any]:
    """Carga TOML de forma segura."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {}


def _load_json(path: Path) -> dict[str, Any]:
    """Carga JSON de forma segura."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def _toml_dumps(data: dict[str, Any]) -> str:
    lines = ["# Configuración de AyusOS", ""]
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            lines.append(f"[{key}]")
            for subkey, subvalue in value.items():
                lines.append(f"{subkey} = {_toml_value(subvalue)}")
            lines.append("")
        else:
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _save_toml_atomic(path: Path, data: dict[str, Any]) -> bool:
    """Guarda TOML atómicamente (temp + rename), sin dependencias externas."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".ayusos-", dir=path.parent, delete=False
        ) as tmp:
            tmp.write(_toml_dumps(data))
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
        return True
    except OSError:
        return False


def load_system_config() -> dict[str, Any]:
    """Carga solo la config del sistema (/etc/ayusos/ayusos.conf)."""
    return _load_toml(SYSTEM_CONFIG_PATH)


def load_user_preferences() -> dict[str, Any]:
    """Carga solo preferencias de usuario (~/.config/aio-debian-gui/preferences.json)."""
    return _load_json(USER_PREFS_PATH)


def get_effective_config() -> AyusOSConfig:
    """Configuración efectiva fusionada: defaults < system < user."""
    merged = SYSTEM_DEFAULTS.copy()
    merged = _deep_merge(merged, load_system_config())
    merged = _deep_merge(merged, load_user_preferences())
    return AyusOSConfig.from_dict(merged)


def save_system_config(config: AyusOSConfig) -> bool:
    """Guarda config de sistema (requiere root)."""
    return _save_toml_atomic(SYSTEM_CONFIG_PATH, config.to_dict())


def save_user_preferences(prefs: dict[str, Any]) -> bool:
    """Guarda preferencias de usuario."""
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".prefs-", dir=USER_CONFIG_DIR, delete=False
        ) as tmp:
            json.dump(prefs, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(USER_PREFS_PATH)
        return True
    except OSError:
        return False


def mark_onboarding_done(version: str, prefs: dict[str, Any] | None = None) -> bool:
    """Guarda las preferencias del asistente y su estado en la misma escritura."""
    if prefs is None:
        prefs = load_user_preferences()
    prefs["onboarding"] = {**prefs.get("onboarding", {}), "completed": True, "version": version}
    return save_user_preferences(prefs)


def is_onboarding_completed() -> bool:
    """Comprueba si el onboarding ya se completó (system o user)."""
    # Prioridad: marcador de sistema > user > defecto
    system = load_system_config()
    if system.get("onboarding", {}).get("completed"):
        return True
    user = load_user_preferences()
    return bool(user.get("onboarding", {}).get("completed"))


def get_onboarding_version() -> str:
    """Versión del onboarding completado."""
    system = load_system_config()
    ver = system.get("onboarding", {}).get("version")
    if ver:
        return ver
    user = load_user_preferences()
    return user.get("onboarding", {}).get("version", "0.0.0")


# Perfiles de aplicaciones predefinidos
APP_PROFILES = {
    "minimal": [],
    "development": [
        "code", "git", "docker.io", "btop", "htop", "kitty", "ghostty",
    ],
    "multimedia": [
        "vlc", "gimp", "handbrake", "celluloid", "audacity", "kdenlive", "obs-studio",
    ],
    "gaming": [
        "steam", "heroic", "lutris", "retroarch", "mangohud", "gamemode",
    ],
    "full": [
        "code", "git", "docker.io", "btop", "htop", "kitty", "ghostty",
        "vlc", "gimp", "handbrake", "celluloid", "audacity", "kdenlive", "obs-studio",
        "steam", "heroic", "lutris", "retroarch", "mangohud", "gamemode",
        "libreoffice-writer", "libreoffice-calc", "libreoffice-impress",
        "onlyoffice-desktopeditors", "thunderbird",
    ],
}


def get_profile_packages(profile: str) -> list[str]:
    """Devuelve lista de paquetes DEB para un perfil."""
    return APP_PROFILES.get(profile, [])


def get_recommended_apps_for_profile(profile: str) -> list[str]:
    """IDs de apps recomendadas (aio-debian-gui) para un perfil."""
    base = ["vlc", "gimp", "celluloid", "btop", "flameshot", "htop"]
    extra = {
        "development": ["code", "git", "kitty", "ghostty"],
        "multimedia": ["handbrake", "kdenlive", "audacity", "obs-studio"],
        "gaming": ["steam", "heroic", "retroarch"],
        "full": ["code", "git", "kitty", "ghostty", "handbrake", "kdenlive",
                 "audacity", "obs-studio", "steam", "heroic", "retroarch",
                 "onlyoffice-desktopeditors", "thunderbird"],
    }
    return base + extra.get(profile, [])


# Validación de valores permitidos
VALID_KERNEL_VARIANTS = {"stable", "backports", "hwe"}
VALID_NVIDIA_MODES = {"auto", "manual", "none"}
VALID_MAINTENANCE_SCHEDULES = {"daily", "weekly", "monthly", "disabled"}
VALID_APP_PROFILES = {"minimal", "development", "multimedia", "gaming", "full"}
VALID_THEMES = {"system", "light", "dark"}
AYUSOS_ACCENT = "red"


def installed_gnome_tasks(user_data_dir=None):
    from aio_core.gnome_extensions import EXTENSIONS

    if user_data_dir is None:
        user_data_dir = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots = [Path(user_data_dir), Path("/usr/share"), *(Path(d) for d in data_dirs.split(":") if d)]
    return {
        task for task, uuid in EXTENSIONS.items()
        if any((root / "gnome-shell/extensions" / uuid / "metadata.json").is_file() for root in roots)
    }


VALID_ACCENTS = {"ayusos", "blue", "green", "orange", "purple", "red", "teal"}


def validate_config(config: AyusOSConfig) -> list[str]:
    """Valida config y devuelve lista de errores (vacía si ok)."""
    errors = []
    if config.kernel.variant not in VALID_KERNEL_VARIANTS:
        errors.append(f"kernel.variant inválido: {config.kernel.variant}")
    if config.nvidia.mode not in VALID_NVIDIA_MODES:
        errors.append(f"nvidia.mode inválido: {config.nvidia.mode}")
    if config.maintenance.schedule not in VALID_MAINTENANCE_SCHEDULES:
        errors.append(f"maintenance.schedule inválido: {config.maintenance.schedule}")
    if config.apps.profile not in VALID_APP_PROFILES:
        errors.append(f"apps.profile inválido: {config.apps.profile}")
    if config.appearance.theme not in VALID_THEMES:
        errors.append(f"appearance.theme inválido: {config.appearance.theme}")
    if config.appearance.accent not in VALID_ACCENTS:
        errors.append(f"appearance.accent inválido: {config.appearance.accent}")
    return errors


# CLI helper para el asistente privilegiado
def cli_get(key: str) -> str | None:
    """Obtiene valor de config efectiva por clave punteada (ej: repos.backports)."""
    config = get_effective_config()
    parts = key.split(".")
    obj: Any = config
    for part in parts:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
    return str(obj) if not isinstance(obj, (dict, list)) else json.dumps(obj)


def cli_set_system(key: str, value: str) -> bool:
    """Establece valor en config de sistema (requiere root)."""
    config = AyusOSConfig.from_dict(load_system_config())
    parts = key.split(".")
    obj: Any = config
    for part in parts[:-1]:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return False
    # Conversión de tipo básica
    target = parts[-1]
    current = getattr(obj, target, None)
    if isinstance(current, bool):
        value = value.lower() in ("true", "1", "yes", "on")
    elif isinstance(current, int):
        value = int(value)
    elif isinstance(current, list):
        value = [v.strip() for v in value.split(",")]
    setattr(obj, target, value)
    return save_system_config(config)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_config.py get|set <key> [value]", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "get" and len(sys.argv) == 3:
        val = cli_get(sys.argv[2])
        if val is not None:
            print(val)
        else:
            sys.exit(1)
    elif cmd == "set" and len(sys.argv) == 4:
        ok = cli_set_system(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)
    else:
        print("Uso: ayusos_config.py get|set <key> [value]", file=sys.stderr)
        sys.exit(1)
