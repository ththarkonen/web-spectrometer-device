import hashlib
import json
import lzma
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "custom-os" / "imager" / "create-imager-manifest.py"
RELEASE_SCRIPT = ROOT / "custom-os" / "create-release-manifest.sh"


def test_create_imager_manifest_uses_cloudinit_rpi_and_hashes(tmp_path: Path) -> None:
    raw = tmp_path / "image.img"
    compressed = tmp_path / "image.img.xz"
    output = tmp_path / "image.rpi-imager-manifest"

    raw_bytes = b"web spectrometer image bytes"
    raw.write_bytes(raw_bytes)
    compressed.write_bytes(lzma.compress(raw_bytes))

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(compressed),
            "--uncompressed-image",
            str(raw),
            "--image-url",
            "https://example.test/image.img.xz",
            "--icon-url",
            "https://example.test/icon.svg",
            "--website",
            "https://example.test",
            "--release-date",
            "2026-05-23",
            "--output",
            str(output),
        ],
        check=True,
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    entry = data["os_list"][0]

    assert entry["init_format"] == "cloudinit-rpi"
    assert entry["url"] == "https://example.test/image.img.xz"
    assert entry["extract_size"] == len(raw_bytes)
    assert entry["extract_sha256"] == hashlib.sha256(raw_bytes).hexdigest()
    assert entry["image_download_sha256"] == hashlib.sha256(compressed.read_bytes()).hexdigest()
    assert "pi3-32bit" in entry["devices"]


def test_create_release_manifest_wrapper_builds_github_release_urls(tmp_path: Path) -> None:
    raw = tmp_path / "web-spectrometer-pi-os-1.2.3.img"
    compressed = tmp_path / "web-spectrometer-pi-os-1.2.3.img.xz"
    output = tmp_path / "web-spectrometer-pi-os-1.2.3.rpi-imager-manifest"

    raw_bytes = b"web spectrometer release image bytes"
    raw.write_bytes(raw_bytes)
    compressed.write_bytes(lzma.compress(raw_bytes))

    subprocess.run(
        [
            "bash",
            str(RELEASE_SCRIPT),
            "--image",
            str(compressed),
            "--uncompressed-image",
            str(raw),
            "--owner",
            "example-owner",
            "--repository",
            "web-spectrometer-device",
            "--tag",
            "v1.2.3",
            "--release-date",
            "2026-05-24",
            "--output",
            str(output),
        ],
        check=True,
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    entry = data["os_list"][0]

    assert entry["init_format"] == "cloudinit-rpi"
    assert (
        entry["url"]
        == "https://github.com/example-owner/web-spectrometer-device/releases/download/v1.2.3/web-spectrometer-pi-os-1.2.3.img.xz"
    )
    assert (
        entry["icon"]
        == "https://raw.githubusercontent.com/example-owner/web-spectrometer-device/v1.2.3/custom-os/imager/web-spectrometer-icon.svg"
    )
    assert entry["website"] == "https://github.com/example-owner/web-spectrometer-device"
    assert entry["extract_size"] == len(raw_bytes)
