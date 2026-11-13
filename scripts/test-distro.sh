#!/usr/bin/env bash
# Comprobaciones de compatibilidad sin modificar el sistema.
set -euo pipefail
cd "$(dirname "$0")/.."
HELPER="$PWD/package/usr/lib/aio-debian-gui/aio-debian-gui-helper"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
cat > "$TMP/debian" <<'EOF'
ID=debian
VERSION_ID="13"
EOF
cat > "$TMP/ubuntu24" <<'EOF'
ID=ubuntu
VERSION_ID="24.04"
EOF
cat > "$TMP/ubuntu26" <<'EOF'
ID=ubuntu
VERSION_ID="26.04"
EOF
cat > "$TMP/unsupported" <<'EOF'
ID=linuxmint
ID_LIKE="ubuntu debian"
VERSION_ID="22"
EOF

for pair in "debian:debian" "ubuntu24:ubuntu" "ubuntu26:ubuntu"; do
  file=${pair%%:*}
  expected=${pair#*:}
  got=$(AIO_TEST_OS_RELEASE="$TMP/$file" bash -c 'source "$1"; leer_distribucion' _ "$HELPER")
  [ "$got" = "$expected" ] || { echo "Distribución incorrecta para $file: $got" >&2; exit 1; }
done
if AIO_TEST_OS_RELEASE="$TMP/unsupported" bash -c 'source "$1"; leer_distribucion' _ "$HELPER" >/dev/null 2>&1; then
  echo 'Una distribución derivada no verificada se aceptó como soportada.' >&2
  exit 1
fi

# Metapaquetes específicos: nunca instalar los de Ubuntu en Debian.
for version in 24 26; do
  result=$(AIO_TEST_OS_RELEASE="$TMP/ubuntu$version" bash -c 'source "$1"; ubuntu_hwe_paquete' _ "$HELPER")
  [ "$result" = "linux-generic-hwe-$version.04" ]
done
if AIO_TEST_OS_RELEASE="$TMP/debian" bash -c 'source "$1"; ubuntu_hwe_paquete' _ "$HELPER" >/dev/null 2>&1; then
  echo 'HWE de Ubuntu disponible en Debian.' >&2
  exit 1
fi

mkdir -p "$TMP/apt/sources.list.d"
cat > "$TMP/apt/sources.list.d/ubuntu.sources" <<'EOF'
Types: deb
URIs: http://archive.ubuntu.com/ubuntu
Suites: noble noble-updates
Components: main universe restricted multiverse
EOF
AIO_TEST_OS_RELEASE="$TMP/ubuntu24" bash -c '
  source "$1"
  estado_repos "$2" || exit 1
  sed -i "s/ multiverse//" "$2/sources.list.d/ubuntu.sources"
  if estado_repos "$2"; then exit 1; fi
' _ "$HELPER" "$TMP/apt"

# Las órdenes de habilitación se prueban solo con funciones simuladas, sin tocar APT.
AIO_TEST_LOG="$TMP/commands.log" AIO_TEST_OS_RELEASE="$TMP/ubuntu24" bash -c '
  source "$1"
  asegurar_listas() { return 0; }
  # Usar una variable de nombre fijo para no depender de PATH ni de software-properties.
  add-apt-repository() { printf "%s\n" "$2" >> "$AIO_TEST_LOG"; }
  paso_ubuntu_repos
  [ "$(wc -l < "$AIO_TEST_LOG")" -eq 3 ]
  grep -qx universe "$AIO_TEST_LOG"
  grep -qx restricted "$AIO_TEST_LOG"
  grep -qx multiverse "$AIO_TEST_LOG"
' _ "$HELPER" 2>/dev/null || {
  echo 'Falló la simulación segura de repositorios Ubuntu.' >&2
  exit 1
}
echo '✔ perfiles Debian/Ubuntu 24.04/26.04 y repositorios Ubuntu verificados sin cambios reales'
