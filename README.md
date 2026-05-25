# Web Spectrometer Device

Device-side Raspberry Pi software for the Web Spectrometer project. This repository is intended as the publishable Pi/API repository, not the browser UI repository.

## Install the Raspberry Pi OS Image

The recommended installation path is the release manifest for Raspberry Pi Imager. The release manifest installation flow has been tested with Raspberry Pi Imager 2.0.7.

1. Open Raspberry Pi Imager.
2. Add the Web Spectrometer manifest using one of these methods:
   - URL method: choose **App Options** -> **Content Repository** -> **Use custom URL**, then paste the release manifest URL.
   - File method: download `web-spectrometer-pi-os-<version>.rpi-imager-manifest` from the GitHub release, then open it by double-clicking the file or choosing **App Options** -> **Content Repository** -> **Use custom file**.
3. Select the Web Spectrometer OS entry from **Choose OS**.
4. Select the microSD card.
5. Open OS customisation and set Wi-Fi credentials.
6. Recommended: set a hostname such as `lab-spectrometer`. Optional: enable SSH and set a login account.
7. Flash the card, boot the Pi, then connect to `http://<hostname>.local:8765/` from a compatible UI or API client.

Detailed installation instructions are in [docs/raspberry-pi-install.md](docs/raspberry-pi-install.md).

The device service:

- captures full raw `RGB888` camera frames,
- extracts raw `uint8` spectrum rows,
- exposes camera/extraction settings,
- supports first-use pairing and token-protected access,
- can be installed manually as a systemd service,
- can be built into a custom Raspberry Pi OS image.

The browser UI is maintained separately. UI clients use this service as an API device target and rely on the contract in [docs/api.md](docs/api.md) or the live FastAPI OpenAPI document at `/openapi.json`.

## Repository Layout

- `pi/`: FastAPI device service and camera backends.
- `spectrometer_core/`: extraction settings and spectrum extraction logic.
- `deploy/`: manual Raspberry Pi service installation and config generation.
- `custom-os/`: pi-gen stage, firstboot provisioning, Imager manifest tooling, and image build wrapper.
- `docs/`: API contract and Raspberry Pi install notes.
- `tests/`: API, extraction, firstboot, and Imager manifest tests.

## Development

Development uses the `web-spectrometer-env` conda environment:

```bash
conda activate web-spectrometer-env
python -m pip install -r requirements-dev.txt
pytest
```

Run the API locally with the mock camera:

```bash
SPECTROMETER_ALLOW_NO_TOKEN=1 python -m pi.camera_service --mock-camera --host 127.0.0.1 --port 8765
```

Local endpoints:

```text
http://127.0.0.1:8765/
http://127.0.0.1:8765/health
http://127.0.0.1:8765/openapi.json
http://127.0.0.1:8765/docs
```

## Manual Raspberry Pi Installation

Manual installation for development or SSH-based upgrades:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-picamera2 rsync avahi-daemon
SERVICE_USER="$USER" bash deploy/install-pi-service.sh
```

The installer copies this repository to `/opt/web-spectrometer`, creates or migrates `/etc/web-spectrometer/config.json`, installs `web-spectrometer.service`, and disables any previous `bluetooth-spectrometer.service`.

Service commands:

```bash
sudo systemctl status web-spectrometer.service
sudo systemctl restart web-spectrometer.service
journalctl -u web-spectrometer.service -f
```

## Custom OS Build

Build wrapper:

```bash
IMAGE_VERSION=1.0.0 custom-os/build-image.sh
```

Release artifacts:

- `web-spectrometer-pi-os-<version>.img.xz`
- `web-spectrometer-pi-os-<version>.img.xz.sha256`
- `web-spectrometer-pi-os-<version>.rpi-imager-manifest`

The public `.rpi-imager-manifest` is the Raspberry Pi Imager entry point. The compressed image remains a release asset because the manifest `url` field points Imager to that image.

End-user installation instructions for the release manifest flow are in [docs/raspberry-pi-install.md](docs/raspberry-pi-install.md). The GitHub release note template is [custom-os/release-template.md](custom-os/release-template.md).

## API Contract

Primary endpoints:

- `GET /health`
- `POST /pairing`
- `GET /settings`
- `PATCH /settings`
- `GET /frame.raw`
- `GET /spectrum`
- `WS /stream?token=ACCESS_CODE`

See [docs/api.md](docs/api.md) for details.

## Pre-Publication Checklist

- Add a `LICENSE`.
- Rebuild the image from this repository and clean-flash test firstboot, pairing, `/frame.raw`, `/spectrum`, `/stream`, and camera LED behavior.
- Keep UI code out of this repository; this repository is API-only device software.
