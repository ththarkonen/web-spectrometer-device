# Raspberry Pi Installation

The recommended installation path is the custom Raspberry Pi OS image. Manual installation remains supported for development, debugging, or upgrading an existing Pi.

## Option 1: Install the Custom OS Image

Requirements:

- Raspberry Pi Zero 2 W or another Raspberry Pi with camera support.
- Raspberry Pi camera connected to the Pi.
- microSD card.
- Raspberry Pi Imager on the computer used to flash the card.
- Wi-Fi credentials for the network the computer and Pi will share.

The release manifest installation flow has been tested with Raspberry Pi Imager 2.0.7.

Manifest entry methods:

- URL method: choose **App Options** -> **Content Repository** -> **Use custom URL**, then paste the release manifest URL.
- File method: download `web-spectrometer-pi-os-<version>.rpi-imager-manifest` from the GitHub release, then open it by double-clicking the file or choosing **App Options** -> **Content Repository** -> **Use custom file**.

Install:

1. Open Raspberry Pi Imager.
2. Add the Web Spectrometer manifest using one of the manifest entry methods.
3. Select the Web Spectrometer OS entry from **Choose OS**.
4. Select the microSD card.
5. Open OS customisation and set Wi-Fi credentials.
6. Recommended: set a hostname such as `lab-spectrometer`. Optional: enable SSH and set a user account.
7. Flash the card.
8. Insert the card into the Pi and power it on.
9. Wait for first boot to finish. The Pi may reboot once if it generated a unique hostname.
10. Connect to the API from a compatible UI or client. The hostname becomes the API URL name, so hostname `lab-spectrometer` is `http://lab-spectrometer.local:8765/`.
11. Pair the device through the UI or by calling `POST /pairing` to choose the access code for this spectrometer.

The public manifest points Raspberry Pi Imager at the release image URL. Manual download of the `.img.xz` file is not required for the manifest-based flow. The `.img.xz` file remains attached to the GitHub release because Imager downloads it from the URL stored in the manifest.

Do not use **Choose OS** -> **Use custom** directly with the `.img.xz` file when you need Wi-Fi/SSH customization in Raspberry Pi Imager 2.x. The manifest is what tells Imager that the image supports Raspberry Pi OS cloud-init customisation.

The setup file contains:

```text
Friendly name: Spectrometer <ID>
Device ID: <id>
Hostname: spectrometer-<id>
URL: http://spectrometer-<id>.local:8765/
Access code: set during first API pairing
```

The setup file is mainly a fallback for finding the generated URL. If you enabled SSH, you can read it at `/boot/firmware/spectrometer-setup.txt` on the Pi. It is also written to the SD card boot partition.

If the `.local` URL does not resolve, find the Pi IP address from your router and use:

```text
http://<pi-ip-address>:8765/
```

A compatible UI or API client can set a friendly name and choose the first access code. The friendly name is separate from the network hostname.

If you set a hostname in Imager, the setup file uses that hostname. If you leave the hostname at the Raspberry Pi OS default, first boot changes it to `spectrometer-<id>` to avoid collisions when multiple spectrometers are on the same network.

Setting a login password or enabling SSH in Imager does not affect the spectrometer service. The service and its Python libraries are already installed in the image and run independently of the login user.

## Multiple Spectrometers

Each custom-image Pi generates a short device ID from a hash of its MAC address and persists it. The raw MAC address is not shown.

Multiple devices on the same Wi-Fi get different hostnames:

```text
http://spectrometer-8f3a91c.local:8765/
http://spectrometer-91f0aa.local:8765/
```

Client applications can save and switch between devices. A typical UI profile stores:

- friendly name,
- API URL,
- access code,
- calibration state.

## Option 2: Manual Installation On Raspberry Pi OS

Use this path if you already have Raspberry Pi OS installed and can SSH into the Pi.

Install system packages:

```bash
sudo apt update
sudo apt install -y --no-install-recommends git python3-venv python3-pip python3-picamera2 rsync avahi-daemon
```

Clone the repository:

```bash
git clone https://github.com/<owner>/<repository>.git web-spectrometer
cd web-spectrometer
```

Install and start the service. Set `SERVICE_USER` to the current user unless the Pi has a `pi` user:

```bash
SERVICE_USER="$USER" bash deploy/install-pi-service.sh
```

The installer:

- copies the project to `/opt/web-spectrometer`,
- creates `/etc/web-spectrometer/config.json` if missing,
- prints the generated access code,
- installs `web-spectrometer.service`,
- enables and starts the service,
- writes the camera LED boot setting,
- serves the device API from the Pi.

API base URL:

```text
http://<pi-hostname>.local:8765/
```

For example:

```text
http://raspberrypi.local:8765/
```

If `.local` does not resolve, use the Pi IP address:

```text
http://<pi-ip-address>:8765/
```

If you missed the generated access code:

```bash
sudo /opt/web-spectrometer/.venv/bin/python -c "import json; print(json.load(open('/etc/web-spectrometer/config.json'))['service']['access_token'])"
```

Check the service:

```bash
sudo systemctl status web-spectrometer.service
curl http://localhost:8765/health
```

Follow logs:

```bash
journalctl -u web-spectrometer.service -f
```

Restart after deploying changes:

```bash
sudo systemctl restart web-spectrometer.service
```

If the installer reports that it configured the camera LED setting, reboot once:

```bash
sudo reboot
```

## API Clients

The Pi serves only the API:

```text
http://<device-hostname-or-ip>:8765/
```

Use `/openapi.json` for the machine-readable contract and `/docs` for interactive API documentation. See [API contract](api.md).

Data endpoints remain token-protected. A separate UI or client is responsible for storing access codes on the computer used to operate the spectrometer.

## Custom OS Build Instructions

Build instructions for release maintainers are in:

```text
custom-os/README.md
```

Upload the release image as a GitHub release artifact together with a SHA256 checksum. Upload the public `.rpi-imager-manifest` as well; it is the file operators download to enable the Raspberry Pi Imager Wi-Fi/SSH setup flow. The `.img.xz` file remains attached because Imager downloads it from the manifest URL.

## References

- Raspberry Pi Imager installation and OS customisation: <https://www.raspberrypi.com/documentation/installation/raspbian/installing-imager.md>
- Raspberry Pi boot partition and configuration files: <https://www.raspberrypi.com/documentation/configuration/computers/raspberry-pi.html>
