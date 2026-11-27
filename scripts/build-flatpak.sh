#!/bin/bash
# Build Flatpak package for AiO Debian GUI
# Usage: ./build-flatpak.sh [--repo REPO_DIR] [--sign KEY_ID] [--gpg-homedir DIR] [--bundle FILE]

set -euo pipefail

cd "$(dirname "$0")/.."

MANIFEST="io.github.julioayusoalende_hue.aio_debian_gui.yml"
REPO_DIR="flatpak-repo"
SIGN_KEY=""
GPG_HOMEDIR=""
BUNDLE_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)
            REPO_DIR="$2"
            shift 2
            ;;
        --sign)
            SIGN_KEY="$2"
            shift 2
            ;;
        --gpg-homedir)
            GPG_HOMEDIR="$2"
            shift 2
            ;;
        --bundle)
            BUNDLE_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--repo REPO_DIR] [--sign KEY_ID] [--gpg-homedir DIR] [--bundle FILE]" >&2
            exit 1
            ;;
    esac
done

# Read version from the Debian control file (authoritative), then CHANGELOG
VERSION=$(sed -n 's/^Version: //p' package/DEBIAN/control | head -1)
VERSION=${VERSION#*:}
if [[ -z "$VERSION" ]]; then
    VERSION=$(sed -n 's/^## \([0-9][0-9.]*\)$/\1/p' CHANGELOG.md | head -1)
fi
VERSION=${VERSION:-"1.6.2"}

echo "Building Flatpak version $VERSION..."

# Set up source date epoch for reproducible builds
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || date +%s)}"

# Create a temporary build directory
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

# Build the Flatpak
flatpak-builder \
    --force-clean \
    --ccache \
    --require-changes \
    --repo="$REPO_DIR" \
    --default-branch=stable \
    --arch=x86_64 \
    --arch=aarch64 \
    --install-deps-from=flathub \
    "$BUILD_DIR/build" \
    "$MANIFEST"

# Update repository summary
flatpak build-update-repo \
    --prune \
    --prune-depth=20 \
    "$REPO_DIR"

if [[ -n "$SIGN_KEY" ]]; then
    GPG_ARGS=()
    [[ -n "$GPG_HOMEDIR" ]] && GPG_ARGS=(--gpg-homedir="$GPG_HOMEDIR")
    flatpak build-update-repo \
        --sign="${SIGN_KEY}" \
        "${GPG_ARGS[@]}" \
        "$REPO_DIR"
fi

# Create single-file bundle if requested
if [[ -n "$BUNDLE_FILE" ]]; then
    flatpak build-bundle \
        "$REPO_DIR" \
        "$BUNDLE_FILE" \
        io.github.julioayusoalende_hue.aio_debian_gui \
        --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo
fi

echo "Flatpak build complete!"
echo "Repository: $REPO_DIR"
[[ -n "$BUNDLE_FILE" ]] && echo "Bundle: $BUNDLE_FILE"
