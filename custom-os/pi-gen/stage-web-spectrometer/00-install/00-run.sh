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
cat > "${ROOTFS_DIR}/etc/web-spectrometer/config.json" <<'EOF'
{
  "service": {
    "host": "0.0.0.0",
    "port": 8765,
    "access_token": "",
    "pairing_required": true,
    "camera_backend": "auto",
    "cors_origins": ["*"]
  },
  "settings": {
    "frame_width": 800,
    "frame_height": 600,
    "output_width": 800,
    "row_center_y": 300,
    "half_height": 1,
    "angle_degrees": 0,
    "reverse_x": false,
    "gain": 1.0,
    "frame_duration_us": 40000
  }
}
EOF
chmod 0600 "${ROOTFS_DIR}/etc/web-spectrometer/config.json"
