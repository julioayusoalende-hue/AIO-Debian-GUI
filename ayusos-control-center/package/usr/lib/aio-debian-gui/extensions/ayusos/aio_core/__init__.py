"""Módulos específicos de AyusOS.

La carga se hace por submódulo para evitar ciclos entre branding, onboarding
y configuración durante el descubrimiento de extensiones.
"""

from .ayusos_config import (
    AyusOSConfig,
    APP_PROFILES,
    get_effective_config,
    is_onboarding_completed,
    load_system_config,
    load_user_preferences,
    mark_onboarding_done,
    save_system_config,
    save_user_preferences,
    validate_config,
)

__all__ = [
    "AyusOSConfig", "APP_PROFILES", "get_effective_config",
    "is_onboarding_completed", "load_system_config", "load_user_preferences",
    "mark_onboarding_done", "save_system_config", "save_user_preferences",
    "validate_config",
]
