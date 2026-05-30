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

patch_pi_gen_docker_binfmt() {
  local build_docker="$1"

  python3 - "$build_docker" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
original = text

text = text.replace(
"""  if ! qemu_arm=$(which qemu-arm) ; then
    echo "qemu-arm not found (please install qemu-user-binfmt)"
    exit 1
  fi
  if [ ! -f /proc/sys/fs/binfmt_misc/register ]; then
""",
"""  if ! qemu_arm=$(which qemu-arm) ; then
    echo "qemu-arm not found on host; relying on privileged pi-gen container binfmt setup"
    qemu_arm=""
  fi
  if [ -n "${qemu_arm}" ] && [ ! -f /proc/sys/fs/binfmt_misc/register ]; then
""",
)

text = text.replace(
"""  if ! grep -q "^interpreter ${qemu_arm}" /proc/sys/fs/binfmt_misc/qemu-arm* ; then
""",
"""  if [ -n "${qemu_arm}" ] && ! grep -q "^interpreter ${qemu_arm}" /proc/sys/fs/binfmt_misc/qemu-arm* ; then
""",
)

old_registration = """    dpkg-reconfigure qemu-user-binfmt &&
    # binfmt_misc is sometimes not mounted with debian trixie image
    (mount binfmt_misc -t binfmt_misc /proc/sys/fs/binfmt_misc || true) &&
"""
new_registration = """    # binfmt_misc is sometimes not mounted with Debian trixie image.
    (mount binfmt_misc -t binfmt_misc /proc/sys/fs/binfmt_misc || true) &&
    if [ -x /usr/lib/systemd/systemd-binfmt ]; then
      /usr/lib/systemd/systemd-binfmt
    else
      dpkg-reconfigure qemu-user-binfmt
    fi &&
"""

if old_registration in text:
    text = text.replace(old_registration, new_registration)
elif "/usr/lib/systemd/systemd-binfmt" not in text:
    raise SystemExit(f"could not patch binfmt registration in {path}")

if text != original:
    path.write_text(text)
PY
}

patch_pi_gen_bootstrap_signature() {
  local common_script="$1"

  python3 - "$common_script" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
original = text

needle = """\tBOOTSTRAP_ARGS+=(--keyring "${STAGE_DIR}/files/raspberrypi.gpg")\n"""
replacement = needle + """\tif [ "${BOOTSTRAP_NO_CHECK_SIG:-0}" = "1" ]; then
\t\tBOOTSTRAP_ARGS+=(--no-check-sig)
\tfi
"""

if "BOOTSTRAP_NO_CHECK_SIG" not in text:
    if needle not in text:
        raise SystemExit(f"could not patch bootstrap signature handling in {path}")
    text = text.replace(needle, replacement, 1)

if text != original:
    path.write_text(text)
PY
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
    patch_pi_gen_docker_binfmt "$PI_GEN_DIR/build-docker.sh"
    patch_pi_gen_bootstrap_signature "$PI_GEN_DIR/scripts/common"
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
    patch_pi_gen_bootstrap_signature "$PI_GEN_DIR/scripts/common"
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
