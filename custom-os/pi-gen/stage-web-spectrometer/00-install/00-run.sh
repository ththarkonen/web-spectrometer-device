#!/bin/bash -e

install -d "${ROOTFS_DIR}/opt/web-spectrometer"
rsync -a --delete --delete-excluded \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude "desktop" \
  --exclude "ui" \
  --exclude "web" \
  "${STAGE_DIR}/00-install/files/app/" \
  "${ROOTFS_DIR}/opt/web-spectrometer/"

install -Dm755 \
  "${STAGE_DIR}/00-install/files/web-spectrometer-firstboot" \
  "${ROOTFS_DIR}/usr/local/sbin/web-spectrometer-firstboot"

install -Dm644 \
  "${STAGE_DIR}/00-install/files/web-spectrometer-firstboot.service" \
  "${ROOTFS_DIR}/etc/systemd/system/web-spectrometer-firstboot.service"

install -Dm644 \
  "${STAGE_DIR}/00-install/files/web-spectrometer.service" \
  "${ROOTFS_DIR}/etc/systemd/system/web-spectrometer.service"

install -d "${ROOTFS_DIR}/etc/web-spectrometer"
