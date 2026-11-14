#!/bin/bash
set -euo pipefail
source package/usr/lib/aio-debian-gui/aio-debian-gui-helper
snapper() { return 1; }
findmnt() { if [[ "$*" == *FSTYPE* ]]; then printf "btrfs\n"; else printf "/\n"; fi; }
if crear_instantanea_previa; then exit 1; fi
echo "Snapshot fail-safe OK"
