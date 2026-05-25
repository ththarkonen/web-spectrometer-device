#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PI_GEN_REPO="${PI_GEN_REPO:-https://github.com/RPi-Distro/pi-gen.git}"
PI_GEN_DIR="${PI_GEN_DIR:-$REPO_DIR/build/pi-image/pi-gen}"
RELEASE_DIR="${RELEASE_DIR:-$REPO_DIR/release}"
BUILD_BACKEND="${BUILD_BACKEND:-docker}"
IMAGE_VERSION="${IMAGE_VERSION:-$(date +%Y.%m.%d)}"
IMAGE_BASENAME="${IMAGE_BASENAME:-web-spectrometer-pi-os-$IMAGE_VERSION}"
RELEASE_DATE="${RELEASE_DATE:-$(date +%F)}"
XZ_THREADS="${XZ_THREADS:-1}"
XZ_LEVEL="${XZ_LEVEL:-1}"
IMAGE_URL="${IMAGE_URL:-}"
ICON_URL="${ICON_URL:-}"
WEBSITE="${WEBSITE:-}"
PIGEN_CLEAN_WORK="${PIGEN_CLEAN_WORK:-1}"
DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-0}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

run_with_sudo_env() {
  sudo env "DOCKER_BUILDKIT=$DOCKER_BUILDKIT" "$@"
}

latest_image() {
  local directory="$1"
  local result=""
  result="$(
    {
      find "$directory" -maxdepth 1 -type f -name '*web-spectrometer*.img' -printf '%T@ %p\n' 2>/dev/null
      find "$directory" -maxdepth 1 -type f -name '*web-spectrometer*.img.xz' -printf '%T@ %p\n' 2>/dev/null
    } \
      | sort -nr \
      | head -n 1 \
      | cut -d' ' -f2-
  )"
  printf '%s\n' "$result"
}

run_with_optional_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  if [ "$BUILD_BACKEND" = "docker" ] && docker info >/dev/null 2>&1; then
    "$@"
    return
  fi
  run_with_sudo_env "$@"
}

require_command git
require_command rsync
require_command python3
require_command sha256sum
require_command xz
if [ "$BUILD_BACKEND" = "docker" ]; then
  require_command docker
fi

if [ ! -d "$PI_GEN_DIR" ]; then
  mkdir -p "$(dirname "$PI_GEN_DIR")"
  git clone --depth 1 "$PI_GEN_REPO" "$PI_GEN_DIR"
fi

if [ ! -f "$PI_GEN_DIR/build-docker.sh" ] || [ ! -f "$PI_GEN_DIR/build.sh" ]; then
  echo "pi-gen checkout is incomplete: $PI_GEN_DIR" >&2
  exit 1
fi

"$SCRIPT_DIR/prepare-pi-gen-stage.sh" "$PI_GEN_DIR"

case "$BUILD_BACKEND" in
  docker)
    (
      cd "$PI_GEN_DIR"
      if [ "$PIGEN_CLEAN_WORK" = "1" ]; then
        docker rm -v pigen_work 2>/dev/null || true
      fi
      export DOCKER_BUILDKIT
      run_with_optional_sudo ./build-docker.sh
    )
    ;;
  native)
    (
      cd "$PI_GEN_DIR"
      run_with_optional_sudo ./build.sh
    )
    ;;
  *)
    echo "BUILD_BACKEND must be 'docker' or 'native', got: $BUILD_BACKEND" >&2
    exit 1
    ;;
esac

DEPLOY_DIR="$PI_GEN_DIR/deploy"
source_image="$(latest_image "$DEPLOY_DIR")"

if [ -z "$source_image" ]; then
  echo "could not find a Web Spectrometer image under $DEPLOY_DIR" >&2
  exit 1
fi

mkdir -p "$RELEASE_DIR"
compressed_image="$RELEASE_DIR/$IMAGE_BASENAME.img.xz"
manifest_uncompressed=()

case "$source_image" in
  *.img)
    xz -T"$XZ_THREADS" -"$XZ_LEVEL" -k -c "$source_image" > "$compressed_image"
    manifest_uncompressed=(--uncompressed-image "$source_image")
    ;;
  *.img.xz)
    cp "$source_image" "$compressed_image"
    sibling_img="${source_image%.xz}"
    if [ -f "$sibling_img" ]; then
      manifest_uncompressed=(--uncompressed-image "$sibling_img")
    fi
    ;;
  *)
    echo "unexpected image artifact: $source_image" >&2
    exit 1
    ;;
esac

(
  cd "$RELEASE_DIR"
  sha256sum "$(basename "$compressed_image")" > "$(basename "$compressed_image").sha256"
  sha256sum *.img.xz > SHA256SUMS
)

for log_name in build.log build-docker.log; do
  if [ -f "$DEPLOY_DIR/$log_name" ]; then
    cp "$DEPLOY_DIR/$log_name" "$RELEASE_DIR/$IMAGE_BASENAME-$log_name"
  fi
done

source_info="$DEPLOY_DIR/$(basename "${source_image%.xz}" .img).info"
if [ -f "$source_info" ]; then
  cp "$source_info" "$RELEASE_DIR/$IMAGE_BASENAME.info"
fi

local_manifest="$RELEASE_DIR/$IMAGE_BASENAME.local.rpi-imager-manifest"
python3 "$SCRIPT_DIR/imager/create-imager-manifest.py" \
  "$compressed_image" \
  "${manifest_uncompressed[@]}" \
  --release-date "$RELEASE_DATE" \
  --output "$local_manifest"

if [ -n "$IMAGE_URL" ]; then
  public_manifest="$RELEASE_DIR/$IMAGE_BASENAME.rpi-imager-manifest"
  manifest_args=(
    "$compressed_image"
    "${manifest_uncompressed[@]}"
    --image-url "$IMAGE_URL"
    --release-date "$RELEASE_DATE"
    --output "$public_manifest"
  )
  if [ -n "$ICON_URL" ]; then
    manifest_args+=(--icon-url "$ICON_URL")
  fi
  if [ -n "$WEBSITE" ]; then
    manifest_args+=(--website "$WEBSITE")
  fi
  python3 "$SCRIPT_DIR/imager/create-imager-manifest.py" "${manifest_args[@]}"
fi

echo "Image: $compressed_image"
echo "Checksum: $compressed_image.sha256"
echo "Local Imager manifest: $local_manifest"
if [ -n "${public_manifest:-}" ]; then
  echo "Release Imager manifest: $public_manifest"
fi
