# Raspberry Pi Imager Manifest

This directory contains the Raspberry Pi Imager manifest generator and image icon assets.

Raspberry Pi Imager 2.x does not expose Wi-Fi/SSH/hostname customization for an arbitrary local `.img.xz` selected through **Use custom**. The manifest enables those customisation options by describing the image as an OS entry with:

```json
"init_format": "cloudinit-rpi"
```

The public manifest must also include a public image `url`. For public releases, the manifest is the Raspberry Pi Imager entry point and Imager downloads the `.img.xz` from that URL.

## Generate Directly

For GitHub releases, the recommended entry point is:

```bash
custom-os/create-release-manifest.sh \
  --image release/web-spectrometer-pi-os-<version>.img.xz \
  --uncompressed-image build/pi-image/pi-gen/deploy/web-spectrometer-pi-os-<version>.img \
  --owner <owner> \
  --repository <repository> \
  --tag <tag> \
  --output release/web-spectrometer-pi-os-<version>.rpi-imager-manifest
```

The image build wrapper invokes `create-imager-manifest.py` during release builds. Manual lower-level invocation:

```bash
python3 custom-os/imager/create-imager-manifest.py \
  release/web-spectrometer-pi-os-<version>.img.xz \
  --uncompressed-image build/pi-image/pi-gen/deploy/web-spectrometer-pi-os-<version>.img \
  --image-url "https://github.com/<owner>/<repository>/releases/download/<tag>/web-spectrometer-pi-os-<version>.img.xz" \
  --icon-url "https://raw.githubusercontent.com/<owner>/<repository>/<tag>/custom-os/imager/web-spectrometer-icon.svg" \
  --website "https://github.com/<owner>/<repository>" \
  --release-date "<YYYY-MM-DD>" \
  --output release/web-spectrometer-pi-os-<version>.rpi-imager-manifest
```

If `--image-url` is omitted, the manifest points at the local image with `file://`. That form is intended for local testing and is not suitable for public releases.

Default device tags are `pi3-32bit`, `pi4-32bit`, and `pi5-32bit`; `pi3-32bit` covers Raspberry Pi Zero 2 W in Imager filtering.
