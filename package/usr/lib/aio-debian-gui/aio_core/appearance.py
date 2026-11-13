"""Detección de preferencias de apariencia sin dependencias gráficas.

La especificación del portal freedesktop usa:
0 = sin preferencia, 1 = oscuro, 2 = claro.
"""

def preferencia_portal(valor):
    if valor == 1:
        return "oscuro"
    if valor == 2:
        return "claro"
    return None


def preferencia_gnome(valor):
    if valor == "prefer-dark":
        return "oscuro"
    if valor == "prefer-light":
        return "claro"
    return None


def tema_de_nombre(nombre):
    """Respaldo aproximado para escritorios sin portal de apariencia."""
    return "oscuro" if "dark" in (nombre or "").lower() or "oscuro" in (nombre or "").lower() else "claro"
