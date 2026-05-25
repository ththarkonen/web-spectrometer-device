#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
from datetime import date
from pathlib import Path


CHUNK_SIZE = 1024 * 1024
DEFAULT_DEVICES = ("pi3-32bit", "pi4-32bit", "pi5-32bit")

DEVICE_PROFILES = [
    {
        "name": "Raspberry Pi Zero 2 W / 3",
        "description": "32-bit Raspberry Pi OS for Raspberry Pi Zero 2 W and Raspberry Pi 3-class boards",
        "tags": ["pi3-32bit"],
        "matching_type": "exclusive",
        "architecture": "armhf",
        "capabilities": ["i2c", "spi", "serial", "usb_otg"],
    },
    {
        "name": "Raspberry Pi 4 / 400",
        "description": "32-bit Raspberry Pi OS for Raspberry Pi 4 and Raspberry Pi 400",
        "tags": ["pi4-32bit"],
        "matching_type": "exclusive",
        "architecture": "armhf",
        "capabilities": ["i2c", "spi", "serial"],
    },
    {
        "name": "Raspberry Pi 5",
        "description": "32-bit Raspberry Pi OS for Raspberry Pi 5",
        "tags": ["pi5-32bit"],
        "matching_type": "exclusive",
        "architecture": "armhf",
        "capabilities": ["i2c", "spi", "serial"],
    },
]


def hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def hash_xz_payload(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with lzma.open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def image_url(path: Path, explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url
    return path.resolve().as_uri()


def icon_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url
    return Path(__file__).with_name("web-spectrometer-icon.svg").resolve().as_uri()


def parse_devices(value: str) -> list[str]:
    devices = [item.strip() for item in value.split(",") if item.strip()]
    if not devices:
        raise argparse.ArgumentTypeError("at least one device tag is required")
    return devices


def device_profiles(device_tags: list[str]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    known_tags = set()

    for profile in DEVICE_PROFILES:
        tags = profile["tags"]
        if not isinstance(tags, list):
            continue
        known_tags.update(str(tag) for tag in tags)
        if any(tag in device_tags for tag in tags):
            selected.append(profile)

    for tag in device_tags:
        if tag not in known_tags:
            selected.append(
                {
                    "name": tag,
                    "description": f"Custom Raspberry Pi Imager device tag: {tag}",
                    "tags": [tag],
                    "matching_type": "exclusive",
                    "architecture": "armhf",
                }
            )

    return selected


def extract_hash(image: Path, uncompressed_image: Path | None) -> tuple[int, str]:
    if uncompressed_image:
        return hash_file(uncompressed_image)

    if image.name.endswith(".xz"):
        sibling = Path(str(image)[:-3])
        if sibling.exists():
            return hash_file(sibling)
        return hash_xz_payload(image)

    return hash_file(image)


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    image = args.image.resolve()
    if not image.exists():
        raise FileNotFoundError(image)

    uncompressed_image = args.uncompressed_image.resolve() if args.uncompressed_image else None
    if uncompressed_image and not uncompressed_image.exists():
        raise FileNotFoundError(uncompressed_image)

    image_download_size, image_download_sha256 = hash_file(image)
    extract_size, extract_sha256 = extract_hash(image, uncompressed_image)

    entry = {
        "name": args.name,
        "description": args.description,
        "icon": icon_url(args.icon_url),
        "url": image_url(image, args.image_url),
        "release_date": args.release_date,
        "extract_size": extract_size,
        "extract_sha256": extract_sha256,
        "image_download_size": image_download_size,
        "image_download_sha256": image_download_sha256,
        "devices": args.devices,
        "init_format": "cloudinit-rpi",
        "architecture": "armhf",
    }
    if args.website:
        entry["website"] = args.website

    return {
        "imager": {
            "default_os": args.name,
            "devices": device_profiles(args.devices),
        },
        "os_list": [entry],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Raspberry Pi Imager manifest for the Web Spectrometer OS image."
    )
    parser.add_argument("image", type=Path, help="Compressed image, usually web-spectrometer-pi-os-<version>.img.xz")
    parser.add_argument(
        "--uncompressed-image",
        type=Path,
        help="Optional extracted .img file. If omitted, a sibling .img is used or the .xz payload is streamed.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("web-spectrometer-pi-os.rpi-imager-manifest"),
        help="Manifest output path.",
    )
    parser.add_argument(
        "--image-url",
        help="Public release URL for the compressed image. Defaults to a local file:// URL.",
    )
    parser.add_argument(
        "--icon-url",
        help="Public URL for the icon. Defaults to a local file:// URL for the bundled SVG.",
    )
    parser.add_argument("--website")
    parser.add_argument("--release-date", default=date.today().isoformat())
    parser.add_argument("--name", default="Web Spectrometer Pi OS Lite")
    parser.add_argument(
        "--description",
        default="Headless Raspberry Pi OS Lite image for the Web Spectrometer device API.",
    )
    parser.add_argument("--devices", type=parse_devices, default=list(DEFAULT_DEVICES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
