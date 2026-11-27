"""Perfiles de hardware y optimizaciones para AyusOS."""

import json
import os
import subprocess
from pathlib import Path

from aio_core.constants import comando_host, leer_texto, paquete_instalado

# Perfiles de hardware predefinidos
HARDWARE_PROFILES = {
    "laptop": {
        "name": "Portátil",
        "description": "Optimizaciones para batería, suspensión, térmicas",
        "packages": ["tlp", "tlp-rdw", "auto-cpufreq", "thermald", "powertop"],
        "services": ["tlp", "thermald", "auto-cpufreq"],
        "tweaks": {
            "tlp_enable": True,
            "autosuspend_usb": True,
            "cpu_governor": "powersave",
        },
    },
    "desktop": {
        "name": "Escritorio",
        "description": "Rendimiento máximo, sin gestión de batería",
        "packages": ["cpufrequtils", "thermald"],
        "services": ["thermald"],
        "tweaks": {
            "cpu_governor": "performance",
        },
    },
    "gaming": {
        "name": "Gaming",
        "description": "Optimizado para juegos: latencia baja, máxima GPU",
        "packages": ["gamemode", "mangohud", "libvulkan1", "vulkan-tools"],
        # GameMode lo activa D-Bus en la sesión que lo solicita.
        "services": [],
        "tweaks": {
            "cpu_governor": "performance",
        },
    },
    "workstation": {
        "name": "Estación de trabajo",
        "description": "Equilibrio rendimiento/estabilidad para cargas profesionales",
        "packages": ["cpufrequtils", "thermald", "numactl", "hwloc"],
        "services": ["thermald"],
        "tweaks": {
            "cpu_governor": "schedutil",
            "transparent_hugepages": "madvise",
        },
    },
    "server": {
        "name": "Servidor",
        "description": "Estabilidad y throughput, sin interfaz gráfica",
        "packages": ["cpufrequtils", "irqbalance", "numactl"],
        "services": ["irqbalance"],
        "tweaks": {
            "cpu_governor": "performance",
            "transparent_hugepages": "always",
            "swappiness": 10,
        },
    },
}


def detect_hardware_profile() -> str:
    """Detecta perfil recomendado según hardware."""
    # Comprobar si es laptop
    try:
        result = subprocess.run(
            comando_host("systemd-detect-virt", "--container"),
            capture_output=True, text=True, timeout=5
        )
        is_container = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        is_container = False

    if is_container:
        return "server"

    # Detectar laptop por batería
    try:
        result = subprocess.run(
            comando_host("ls", "/sys/class/power_supply/"),
            capture_output=True, text=True, timeout=5
        )
        has_battery = any("BAT" in line or "battery" in line.lower()
                          for line in result.stdout.split("\n"))
    except (OSError, subprocess.SubprocessError):
        has_battery = False

    # Detectar GPU NVIDIA
    has_nvidia = False
    try:
        result = subprocess.run(
            comando_host("lspci", "-nn"),
            capture_output=True, text=True, timeout=5
        )
        has_nvidia = "10de:" in result.stdout
    except (OSError, subprocess.SubprocessError):
        pass

    # Detectar si es primarily gaming (Steam instalado, etc.)
    is_gaming = paquete_instalado("steam") or paquete_instalado("lutris")

    if has_battery:
        return "laptop"
    elif is_gaming and has_nvidia:
        return "gaming"
    elif paquete_instalado("gnome-shell"):
        return "desktop"
    else:
        return "server"


def get_hardware_info() -> dict:
    """Información detallada de hardware."""
    info = {}

    # CPU
    try:
        cpuinfo = leer_texto("/proc/cpuinfo") or ""
        import re
        model = re.search(r"model name\s*:\s*(.+)", cpuinfo)
        info["cpu_model"] = model.group(1).strip() if model else "Desconocido"
        info["cpu_cores"] = len(re.findall(r"^processor\s*:", cpuinfo, re.MULTILINE))
    except Exception:
        info["cpu_model"] = "Desconocido"
        info["cpu_cores"] = 0

    # RAM
    try:
        meminfo = leer_texto("/proc/meminfo") or ""
        import re
        total = re.search(r"MemTotal:\s+(\d+)", meminfo)
        available = re.search(r"MemAvailable:\s+(\d+)", meminfo)
        info["ram_total_gb"] = round(int(total.group(1)) / 1024 / 1024, 1) if total else 0
        info["ram_available_gb"] = round(int(available.group(1)) / 1024 / 1024, 1) if available else 0
    except Exception:
        info["ram_total_gb"] = 0
        info["ram_available_gb"] = 0

    # GPU
    try:
        result = subprocess.run(
            comando_host("lspci", "-nn", "-d", "::0300"),
            capture_output=True, text=True, timeout=5
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            if line:
                gpus.append(line.split(":", 2)[-1].strip())
        info["gpus"] = gpus
    except (OSError, subprocess.SubprocessError):
        info["gpus"] = []

    # Disco
    try:
        result = subprocess.run(
            comando_host("lsblk", "-d", "-o", "NAME,SIZE,TYPE,MODEL", "-J"),
            capture_output=True, text=True, timeout=5
        )
        import json
        data = json.loads(result.stdout)
        info["disks"] = data.get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        info["disks"] = []

    # Batería
    try:
        result = subprocess.run(
            comando_host("ls", "/sys/class/power_supply/"),
            capture_output=True, text=True, timeout=5
        )
        batteries = [d for d in result.stdout.split("\n") if "BAT" in d]
        info["has_battery"] = len(batteries) > 0
        info["battery_devices"] = batteries
    except (OSError, subprocess.SubprocessError):
        info["has_battery"] = False
        info["battery_devices"] = []

    # Virtualización
    try:
        result = subprocess.run(
            comando_host("systemd-detect-virt"),
            capture_output=True, text=True, timeout=5
        )
        info["virtualization"] = result.stdout.strip() or "none"
    except (OSError, subprocess.SubprocessError):
        info["virtualization"] = "unknown"

    return info


def apply_hardware_profile(profile_id: str) -> tuple[bool, str]:
    """Aplica un perfil de hardware (instala paquetes, habilita servicios, tweaks)."""
    if profile_id not in HARDWARE_PROFILES:
        return False, f"Perfil desconocido: {profile_id}"

    if os.geteuid() != 0:
        return False, "Se requieren privilegios de administrador para aplicar el perfil."

    profile = HARDWARE_PROFILES[profile_id]
    errors = []

    # Instalar paquetes
    for pkg in profile["packages"]:
        try:
            result = subprocess.run(
                comando_host("apt-get", "-o", "DPkg::Lock::Timeout=60",
                             "install", "-y", "--no-remove", pkg),
                capture_output=True, text=True, timeout=120,
                stdin=subprocess.DEVNULL,
                env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
            )
            if result.returncode != 0:
                errors.append(f"Paquete {pkg}: {result.stderr[:200]}")
        except (OSError, subprocess.SubprocessError) as e:
            errors.append(f"Paquete {pkg}: {e}")

    # Habilitar servicios
    for svc in profile["services"]:
        try:
            result = subprocess.run(
                comando_host("systemctl", "enable", "--now", svc),
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                errors.append(f"Servicio {svc}: {result.stderr[:200]}")
        except (OSError, subprocess.SubprocessError) as e:
            errors.append(f"Servicio {svc}: {e}")

    # Aplicar tweaks
    tweaks = profile["tweaks"]

    # CPU governor
    if "cpu_governor" in tweaks:
        gov = tweaks["cpu_governor"]
        try:
            if paquete_instalado("cpufrequtils"):
                subprocess.run(
                    comando_host("cpufreq-set", "-r", "-g", gov),
                    check=True, timeout=10
                )
            # También via sysfs
            for cpu in Path("/sys/devices/system/cpu").glob("cpu[0-9]*"):
                gov_path = cpu / "cpufreq" / "scaling_governor"
                if gov_path.exists():
                    gov_path.write_text(gov)
        except (OSError, subprocess.SubprocessError, PermissionError):
            errors.append(f"CPU governor {gov}: sin permisos")

    # TLP config
    if tweaks.get("tlp_enable"):
        try:
            tlp_conf = Path("/etc/tlp.conf")
            if tlp_conf.exists():
                content = tlp_conf.read_text()
                content = content.replace("#TLP_ENABLE=1", "TLP_ENABLE=1")
                tlp_conf.write_text(content)
        except OSError:
            errors.append("TLP config: error escribiendo")

    if errors:
        return False, f"Errores aplicando perfil: {'; '.join(errors[:3])}"
    return True, f"Perfil '{profile['name']}' aplicado correctamente"


def get_current_profile_status() -> dict:
    """Estado actual de perfiles y servicios."""
    detected = detect_hardware_profile()

    # Verificar qué servicios están activos
    active_services = {}
    for profile in HARDWARE_PROFILES.values():
        for svc in profile["services"]:
            try:
                result = subprocess.run(
                    comando_host("systemctl", "is-active", svc),
                    capture_output=True, text=True, timeout=5
                )
                active_services[svc] = result.returncode == 0 and "active" in result.stdout
            except (OSError, subprocess.SubprocessError):
                active_services[svc] = False

    return {
        "detected": detected,
        "profiles": {k: v["name"] for k, v in HARDWARE_PROFILES.items()},
        "active_services": active_services,
        "hardware_info": get_hardware_info(),
    }


# CLI para helper
def cli_hardware_info() -> str:
    return json.dumps(get_hardware_info(), indent=2)


def cli_detect_profile() -> str:
    return json.dumps({"profile": detect_hardware_profile()})


def cli_apply_profile(profile_id: str) -> str:
    ok, msg = apply_hardware_profile(profile_id)
    return json.dumps({"success": ok, "message": msg})


def cli_profile_status() -> str:
    return json.dumps(get_current_profile_status(), indent=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: ayusos_hardware.py info|detect|apply|status", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "info":
        print(cli_hardware_info())
    elif cmd == "detect":
        print(cli_detect_profile())
    elif cmd == "apply":
        if len(sys.argv) < 3:
            print("Falta profile_id", file=sys.stderr)
            sys.exit(1)
        print(cli_apply_profile(sys.argv[2]))
    elif cmd == "status":
        print(cli_profile_status())
    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        sys.exit(1)
