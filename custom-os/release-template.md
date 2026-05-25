# Web Spectrometer Pi OS Release

Attach the generated image and checksum to the GitHub release:

- `web-spectrometer-pi-os-<version>.img.xz`
- `web-spectrometer-pi-os-<version>.rpi-imager-manifest`
- `web-spectrometer-pi-os-<version>.img.xz.sha256`

## Install

The release manifest installation flow has been tested with Raspberry Pi Imager 2.0.7.

Manifest entry methods:

- URL method: choose **App Options** -> **Content Repository** -> **Use custom URL**, then paste this manifest URL.
- File method: download the `.rpi-imager-manifest` file, then open it by double-clicking the file or choosing **App Options** -> **Content Repository** -> **Use custom file**.

1. Install Raspberry Pi Imager.
2. Add the Web Spectrometer manifest using one of the manifest entry methods.
3. Select the Web Spectrometer OS entry and the SD card.
4. Open OS customisation and set Wi-Fi credentials for the network the computer will also use.
5. Recommended: set a hostname such as `lab-spectrometer`. Optional: enable SSH and set a login account.
6. Flash the image.
7. Boot the Pi and wait for the first-boot reboot to finish.
8. Connect a compatible UI or API client to `http://<hostname>.local:8765/`, for example `http://lab-spectrometer.local:8765/`.
9. Choose the access code during first API pairing.

The `.img.xz` file does not need to be downloaded manually when using the public manifest. Raspberry Pi Imager downloads the image from the URL stored in the manifest.

Do not select the `.img.xz` through **Use custom** if you need Imager to configure Wi-Fi. The manifest carries the `cloudinit-rpi` metadata that enables OS customisation.

If you set a hostname in Imager, the URL has the form:

```text
http://<hostname>.local:8765/
```

If you leave the hostname at the Raspberry Pi OS default, first boot generates a unique hostname:

```text
http://spectrometer-<device-id>.local:8765/
```

The generated hostname is written to `spectrometer-setup.txt` on the SD card boot partition. If SSH was enabled in Imager, the same file is available at `/boot/firmware/spectrometer-setup.txt` on the Pi.

If `.local` does not resolve, use the Pi IP address:

```text
http://<pi-ip-address>:8765/
```

The device API contract is available at `/openapi.json`, and interactive API documentation is available at `/docs`.
