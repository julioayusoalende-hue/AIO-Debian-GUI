#!/bin/bash
set -euo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
snapper() { return 1; }
findmnt() { printf "btrfs\n"; }
if crear_instantanea_previa; then exit 1; fi
echo "Snapshot fail-safe OK"
