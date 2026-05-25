#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATOR="$SCRIPT_DIR/imager/create-imager-manifest.py"

usage() {
  cat <<'EOF'
Create a public Raspberry Pi Imager manifest for a GitHub release image.

Usage:
  custom-os/create-release-manifest.sh --image PATH --owner OWNER --repository REPOSITORY --tag TAG [options]

Required arguments:
  --image PATH                   Compressed .img.xz release artifact.
  --owner OWNER                  GitHub owner or organization.
  --repository REPOSITORY        GitHub repository name.
  --tag TAG                      GitHub release tag, for example v1.0.0.

Optional arguments:
  --uncompressed-image PATH      Extracted .img file used for extract hash and size.
  --output PATH                  Manifest output path.
  --asset-name NAME              Release asset filename. Defaults to the image basename.
  --website URL                  Project website. Defaults to the GitHub repository URL.
  --icon-url URL                 Public Raspberry Pi Imager icon URL.
  --release-date YYYY-MM-DD      Release date. Defaults to the current date.
  --name NAME                    Raspberry Pi Imager OS entry name.
  --description TEXT             Raspberry Pi Imager OS entry description.
  --devices CSV                  Raspberry Pi Imager device tags.
  -h, --help                     Show this help text.

The generated manifest contains init_format=cloudinit-rpi, which enables
Raspberry Pi Imager OS customisation for Wi-Fi, hostname, SSH, user, and
password settings.
EOF
}

require_value() {
  local option="$1"
  local value="${2:-}"
  if [ -z "$value" ]; then
    echo "$option requires a value" >&2
    exit 2
  fi
}

image_path=""
uncompressed_image=""
output_path=""
owner=""
repository=""
tag=""
asset_name=""
website=""
icon_url=""
release_date="$(date +%F)"
entry_name=""
description=""
devices=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image)
      require_value "$1" "${2:-}"
      image_path="$2"
      shift 2
      ;;
    --uncompressed-image)
      require_value "$1" "${2:-}"
      uncompressed_image="$2"
      shift 2
      ;;
    --output)
      require_value "$1" "${2:-}"
      output_path="$2"
      shift 2
      ;;
    --owner)
      require_value "$1" "${2:-}"
      owner="$2"
      shift 2
      ;;
    --repository)
      require_value "$1" "${2:-}"
      repository="$2"
      shift 2
      ;;
    --tag)
      require_value "$1" "${2:-}"
      tag="$2"
      shift 2
      ;;
    --asset-name)
      require_value "$1" "${2:-}"
      asset_name="$2"
      shift 2
      ;;
    --website)
      require_value "$1" "${2:-}"
      website="$2"
      shift 2
      ;;
    --icon-url)
      require_value "$1" "${2:-}"
      icon_url="$2"
      shift 2
      ;;
    --release-date)
      require_value "$1" "${2:-}"
      release_date="$2"
      shift 2
      ;;
    --name)
      require_value "$1" "${2:-}"
      entry_name="$2"
      shift 2
      ;;
    --description)
      require_value "$1" "${2:-}"
      description="$2"
      shift 2
      ;;
    --devices)
      require_value "$1" "${2:-}"
      devices="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$image_path" ] || [ -z "$owner" ] || [ -z "$repository" ] || [ -z "$tag" ]; then
  echo "--image, --owner, --repository, and --tag are required" >&2
  usage >&2
  exit 2
fi

if [ ! -f "$image_path" ]; then
  echo "image not found: $image_path" >&2
  exit 1
fi

if [ -n "$uncompressed_image" ] && [ ! -f "$uncompressed_image" ]; then
  echo "uncompressed image not found: $uncompressed_image" >&2
  exit 1
fi

if [ -z "$asset_name" ]; then
  asset_name="$(basename "$image_path")"
fi

if [ -z "$website" ]; then
  website="https://github.com/$owner/$repository"
fi

if [ -z "$icon_url" ]; then
  icon_url="https://raw.githubusercontent.com/$owner/$repository/$tag/custom-os/imager/web-spectrometer-icon.svg"
fi

if [ -z "$output_path" ]; then
  image_dir="$(dirname "$image_path")"
  image_base="$(basename "$asset_name")"
  image_base="${image_base%.img.xz}"
  image_base="${image_base%.xz}"
  image_base="${image_base%.img}"
  output_path="$image_dir/$image_base.rpi-imager-manifest"
fi

image_url="https://github.com/$owner/$repository/releases/download/$tag/$asset_name"

manifest_args=(
  "$image_path"
  --image-url "$image_url"
  --icon-url "$icon_url"
  --website "$website"
  --release-date "$release_date"
  --output "$output_path"
)

if [ -n "$uncompressed_image" ]; then
  manifest_args+=(--uncompressed-image "$uncompressed_image")
fi
if [ -n "$entry_name" ]; then
  manifest_args+=(--name "$entry_name")
fi
if [ -n "$description" ]; then
  manifest_args+=(--description "$description")
fi
if [ -n "$devices" ]; then
  manifest_args+=(--devices "$devices")
fi

python3 "$GENERATOR" "${manifest_args[@]}"
