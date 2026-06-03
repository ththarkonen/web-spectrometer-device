#!/bin/bash -e

python3 -m venv --system-site-packages /opt/web-spectrometer/.venv

systemctl enable web-spectrometer-firstboot.service
systemctl enable web-spectrometer.service
