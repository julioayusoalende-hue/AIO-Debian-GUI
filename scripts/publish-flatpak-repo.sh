#!/usr/bin/env bash
# Publica un repositorio Flatpak firmado en una carpeta de GitHub Pages.
# Uso: scripts/publish-flatpak-repo.sh <directorio-gh-pages>
# Requiere GPG_PRIVATE_KEY importada en GNUPGHOME y GPG_PASSPHRASE opcional.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:?Uso: $0 <directorio-gh-pages>}"
SITE="$(realpath "$SITE")"
APP_ID=io.github.julioayusoalende_hue.aio_debian_gui
BASE_URL=https://julioayusoalende-hue.github.io/AIO-Debian-GUI
REPO_URL="$BASE_URL/flatpak-repo"
REPO="$SITE/flatpak-repo"
mkdir -p "$REPO" "$SITE"
PUBLIC_KEY="$ROOT/package/usr/share/keyrings/aio-debian-gui.gpg"
EXPECTED_FPR="$(gpg --show-keys --with-colons "$PUBLIC_KEY" | awk -F: '$1=="fpr"{print $10;exit}')"
test -n "$EXPECTED_FPR"
gpg --batch --list-secret-keys "$EXPECTED_FPR" >/dev/null 2>&1 || {
  echo "ERROR: falta la clave privada GPG correspondiente a $EXPECTED_FPR." >&2
  exit 1
}
# Reutilizar la clave pública estable garantiza que los clientes confíen
# en futuras versiones. Nunca generar una clave efímera en CI.
export GPG_TTY="$(tty 2>/dev/null || true)"
if [[ -n "${GPG_PASSPHRASE:-}" ]]; then
  export FLATPAK_GPG_PASSPHRASE="$GPG_PASSPHRASE"
fi
flatpak-builder --user --force-clean --disable-rofiles-fuse \
  --install-deps-from=flathub \
  --gpg-sign="$EXPECTED_FPR" \
  --repo="$REPO" \
  "$ROOT/flatpak-build-publish" \
  "$ROOT/flatpak/$APP_ID.yml"

flatpak build-update-repo --title="AiO Debian GUI" \
  --gpg-sign="$EXPECTED_FPR" "$REPO"

GPG_KEY="$(gpg --batch --export "$EXPECTED_FPR" | base64 -w0)"
cat > "$SITE/aio-debian-gui.flatpakrepo" <<EOF
[Flatpak Repo]
Title=AiO Debian GUI
Name=aio-debian-gui
Url=$REPO_URL
Homepage=https://github.com/julioayusoalende-hue/AIO-Debian-GUI
GPGKey=$GPG_KEY
EOF
cat > "$SITE/aio-debian-gui.flatpakref" <<EOF
[Flatpak Ref]
Name=$APP_ID
Branch=stable
Title=AiO Debian GUI
Url=$REPO_URL
IsRuntime=false
RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo
GPGKey=$GPG_KEY
EOF
mkdir -p "$ROOT/dist"
flatpak build-bundle --repo-url="$REPO_URL" \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  "$REPO" "$ROOT/dist/aio-debian-gui_1.0.16_x86_64.flatpak" "$APP_ID" stable
touch "$SITE/.nojekyll"
echo "Repositorio Flatpak firmado preparado en $REPO"
