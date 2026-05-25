# Custom Raspberry Pi OS Image

This directory packages the Web Spectrometer device API service into a headless Raspberry Pi OS Lite image using pi-gen.

## Contents

- `build-image.sh`: wrapper around pi-gen for release builds.
- `create-release-manifest.sh`: creates a public Raspberry Pi Imager manifest for a GitHub release image.
- `prepare-pi-gen-stage.sh`: copies this repository into a pi-gen checkout and prepares the custom stage.
- `pi-gen/`: custom pi-gen stage template.
- `firstboot/`: one-shot provisioning script and service.
- `systemd/`: `web-spectrometer.service` unit for the appliance image.
- `imager/`: Raspberry Pi Imager manifest generator and icon.
- `release-template.md`: release notes template.

## Firstboot Behavior

The image installs `web-spectrometer-firstboot.service`. On first boot it:

- creates `/etc/web-spectrometer/device-id`,
- sets a generated hostname only when Imager did not set a custom hostname,
- creates `/etc/web-spectrometer/config.json` in pairing-required mode if missing,
- writes `/boot/firmware/spectrometer-setup.txt` or `/boot/spectrometer-setup.txt`,
- appends the camera LED boot setting to `config.txt`,
- enables and starts `web-spectrometer.service`,
- disables itself after successful provisioning,
- reboots once when hostname or boot config changed.

The generated setup file contains the API URL and states that the access code is set during first API pairing. It does not contain a token in the default pairing flow.

## Build Command

Install the host build prerequisites on a Debian or Ubuntu build machine:

```bash
sudo apt update
sudo apt install -y git rsync python3 xz-utils qemu-user-binfmt qemu-user-static binfmt-support docker.io
```

From the device repository root:

```bash
IMAGE_VERSION=1.0.0 custom-os/build-image.sh
```

Supported environment overrides:

```bash
PI_GEN_DIR=/path/to/pi-gen IMAGE_VERSION=1.0.0 custom-os/build-image.sh
BUILD_BACKEND=native IMAGE_VERSION=1.0.0 custom-os/build-image.sh
PIGEN_CLEAN_WORK=1 IMAGE_VERSION=1.0.0 custom-os/build-image.sh
DOCKER_BUILDKIT=1 IMAGE_VERSION=1.0.0 custom-os/build-image.sh
```

The wrapper clones pi-gen into `build/pi-image/pi-gen` when the checkout is absent, prepares the stage, runs pi-gen, writes artifacts under `release/`, and creates a local manifest for testing.

For Docker builds, the wrapper defaults `DOCKER_BUILDKIT` to `0` to match pi-gen's direct `build-docker.sh` flow on Ubuntu hosts. Use `DOCKER_BUILDKIT=1` only when the local Docker installation requires BuildKit.

## Public Release Manifest

For a public GitHub release, the build wrapper can create the manifest when public URLs are provided:

```bash
IMAGE_VERSION=1.0.0 \
IMAGE_URL="https://github.com/<owner>/<repository>/releases/download/v1.0.0/web-spectrometer-pi-os-1.0.0.img.xz" \
ICON_URL="https://raw.githubusercontent.com/<owner>/<repository>/v1.0.0/custom-os/imager/web-spectrometer-icon.svg" \
WEBSITE="https://github.com/<owner>/<repository>" \
custom-os/build-image.sh
```

For an existing image artifact, create the release manifest with explicit GitHub release parameters:

```bash
custom-os/create-release-manifest.sh \
  --image release/web-spectrometer-pi-os-1.0.0.img.xz \
  --uncompressed-image build/pi-image/pi-gen/deploy/web-spectrometer-pi-os-1.0.0.img \
  --owner <owner> \
  --repository <repository> \
  --tag v1.0.0 \
  --output release/web-spectrometer-pi-os-1.0.0.rpi-imager-manifest
```

Release assets:

- `web-spectrometer-pi-os-1.0.0.img.xz`
- `web-spectrometer-pi-os-1.0.0.img.xz.sha256`
- `web-spectrometer-pi-os-1.0.0.rpi-imager-manifest`

For the public release flow, distribute the `.rpi-imager-manifest` as the Raspberry Pi Imager entry point. The `.img.xz` must also be uploaded as a release asset because the manifest `url` field points Imager to that image.

## Manual pi-gen Flow

Manual pi-gen inspection/build flow:

```bash
custom-os/prepare-pi-gen-stage.sh /path/to/pi-gen
cd /path/to/pi-gen
sudo ./build-docker.sh
```

The helper creates `pi-gen/config` from `custom-os/pi-gen/config.example` when absent and appends a random `FIRST_USER_PASS` so the image remains non-interactive and headless without publishing a shared password.

## Release Checks

Pre-publication checks:

- Clean-flash the image with the public manifest path.
- Confirm Imager customization offers Wi-Fi, hostname, SSH, user, and password.
- Confirm firstboot writes `/boot/firmware/spectrometer-setup.txt`.
- Confirm `web-spectrometer.service` starts on first boot.
- Confirm `/health`, `/settings`, `/frame.raw`, `/spectrum`, and `/stream`.
- Confirm pairing starts with `pairing_required: true` and becomes false after `POST /pairing`.
