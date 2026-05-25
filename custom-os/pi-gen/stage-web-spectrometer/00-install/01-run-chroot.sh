#!/bin/bash -e

python3 -m venv --system-site-packages /opt/web-spectrometer/.venv
/opt/web-spectrometer/.venv/bin/python -m pip install --upgrade pip
/opt/web-spectrometer/.venv/bin/python -m pip install -r /opt/web-spectrometer/requirements-pi.txt

systemctl enable web-spectrometer-firstboot.service
systemctl enable web-spectrometer.service
