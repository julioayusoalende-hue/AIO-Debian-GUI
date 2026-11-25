#!/usr/bin/env bash
# Pruebas de limpieza segura sin tocar APT, journals, Flatpak ni Snap reales.
set -euo pipefail
cd "$(dirname "$0")/.."
HELPER="$PWD/package/usr/lib/aio-debian-gui/aio-debian-gui-helper"
source "$HELPER"

TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT

# APT y journal: solo comprobamos los argumentos, con comandos simulados.
apt-get() { printf 'apt-get %s\n' "$*" >> "$TMP/apt.log"; }
journalctl() { printf 'journalctl %s\n' "$*" >> "$TMP/journal.log"; }
paso_clean_apt >/dev/null
paso_clean_journal >/dev/null
grep -Fxq 'apt-get clean' "$TMP/apt.log"
grep -Fxq 'journalctl --vacuum-time=30d' "$TMP/journal.log"

# Limpieza personal: ejecutar como el usuario simulado equivale a ejecutar
# directamente porque el HOME temporal pertenece a este mismo usuario.
HOME_TEST="$TMP/home"
OUTSIDE="$TMP/outside"
mkdir -p "$HOME_TEST/.local/share/Trash/files" "$HOME_TEST/.cache/thumbnails/normal" "$OUTSIDE"
printf 'old\n' > "$HOME_TEST/.local/share/Trash/files/old.txt"
printf 'new\n' > "$HOME_TEST/.local/share/Trash/files/new.txt"
printf 'old\n' > "$HOME_TEST/.cache/thumbnails/normal/old.png"
printf 'new\n' > "$HOME_TEST/.cache/thumbnails/normal/new.png"
touch -d '10 days ago' "$HOME_TEST/.cache/thumbnails/normal/old.png"
printf 'outside\n' > "$OUTSIDE/keep.txt"
pkexec_uid() { echo 1000; }
getent() {
    if [ "$1" = passwd ]; then
        printf 'test:x:1000:1000:Test:%s:/bin/bash\n' "$HOME_TEST"
    else
        command getent "$@"
    fi
}
ejecutar_como_usuario_solicitante() { "$@"; }

paso_clean_trash >/dev/null
test ! -e "$HOME_TEST/.local/share/Trash/files/old.txt"
test ! -e "$HOME_TEST/.local/share/Trash/files/new.txt"
paso_clean_thumbnails >/dev/null
test ! -e "$HOME_TEST/.cache/thumbnails/normal/old.png"
test -e "$HOME_TEST/.cache/thumbnails/normal/new.png"

# Enlace directo: se borra el enlace, nunca el destino.
rm -rf "$HOME_TEST/.local/share/Trash"
ln -s "$OUTSIDE" "$HOME_TEST/.local/share/Trash"
paso_clean_trash >/dev/null
test ! -L "$HOME_TEST/.local/share/Trash"
test -e "$OUTSIDE/keep.txt"

# Padre enlazado fuera del HOME: se rechaza antes de borrar nada.
rm -rf "$HOME_TEST/.local/share"
mkdir -p "$OUTSIDE/share"
ln -s "$OUTSIDE/share" "$HOME_TEST/.local/share"
mkdir -p "$OUTSIDE/share/Trash"
printf 'outside\n' > "$OUTSIDE/share/Trash/keep.txt"
if paso_clean_trash >/dev/null 2>&1; then
    echo 'La limpieza aceptó una ruta fuera del HOME' >&2
    exit 1
fi
test -e "$OUTSIDE/share/Trash/keep.txt"

# Flatpak: se comprueba system + usuario, sin ejecutar el binario real.
flatpak() { printf 'flatpak %s\n' "$*" >> "$TMP/flatpak.log"; }
ejecutar_flatpak_usuario() { printf 'user %s\n' "$*" >> "$TMP/flatpak.log"; }
paso_clean_flatpak >/dev/null
grep -Fxq 'flatpak --system uninstall --unused -y' "$TMP/flatpak.log"
grep -Fxq 'user uninstall --unused -y' "$TMP/flatpak.log"

echo "✔ Limpieza segura: APT, journal, papelera, miniaturas, enlaces y Flatpak"
