import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "custom-os" / "firstboot" / "web-spectrometer-firstboot"


def run_firstboot(
    tmp_path: Path,
    hostname: str,
    systemctl: str = "/bin/true",
    extra_env: dict[str, str] | None = None,
) -> tuple[Path, Path, Path]:
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    boot_dir = tmp_path / "boot"
    hostname_file = tmp_path / "hostname"
    hosts_file = tmp_path / "hosts"

    config_dir.mkdir()
    state_dir.mkdir()
    boot_dir.mkdir()
    hostname_file.write_text(f"{hostname}\n", encoding="utf-8")
    hosts_file.write_text("127.0.0.1\tlocalhost\n", encoding="utf-8")
    (state_dir / "device-id").write_text("abc123\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "WEB_SPECTROMETER_APP_DIR": str(tmp_path / "missing-app"),
            "WEB_SPECTROMETER_CONFIG_DIR": str(config_dir),
            "WEB_SPECTROMETER_CONFIG_PATH": str(config_dir / "config.json"),
            "WEB_SPECTROMETER_STATE_DIR": str(state_dir),
            "WEB_SPECTROMETER_DEVICE_ID_FILE": str(state_dir / "device-id"),
            "WEB_SPECTROMETER_COMPLETE_FILE": str(state_dir / "firstboot-complete"),
            "WEB_SPECTROMETER_HOSTNAME_FILE": str(hostname_file),
            "WEB_SPECTROMETER_HOSTS_FILE": str(hosts_file),
            "WEB_SPECTROMETER_BOOT_DIR": str(boot_dir),
            "WEB_SPECTROMETER_SYSTEMCTL": systemctl,
            "WEB_SPECTROMETER_DISABLE_CAMERA_LED": "0",
        }
    )
    if extra_env:
        env.update(extra_env)

    subprocess.run(["bash", str(SCRIPT)], check=True, env=env)
    return hostname_file, boot_dir / "spectrometer-setup.txt", config_dir / "config.json"


def test_firstboot_keeps_existing_hostname(tmp_path: Path) -> None:
    hostname_file, setup_file, _ = run_firstboot(tmp_path, "raspberrypi")

    assert hostname_file.read_text(encoding="utf-8").strip() == "raspberrypi"
    assert "API URL: http://raspberrypi.local:8765/" in setup_file.read_text(encoding="utf-8")


def test_firstboot_keeps_spectrometer_hostname(tmp_path: Path) -> None:
    hostname_file, setup_file, _ = run_firstboot(tmp_path, "spectrometer")

    assert hostname_file.read_text(encoding="utf-8").strip() == "spectrometer"
    assert "API URL: http://spectrometer.local:8765/" in setup_file.read_text(encoding="utf-8")


def test_firstboot_keeps_imager_custom_hostname(tmp_path: Path) -> None:
    hostname_file, setup_file, config_file = run_firstboot(tmp_path, "lab-spectrometer")

    assert hostname_file.read_text(encoding="utf-8").strip() == "lab-spectrometer"
    assert "API URL: http://lab-spectrometer.local:8765/" in setup_file.read_text(encoding="utf-8")
    assert "Access code: set during first API pairing" in setup_file.read_text(encoding="utf-8")
    assert '"access_token": ""' in config_file.read_text(encoding="utf-8")
    assert '"pairing_required": true' in config_file.read_text(encoding="utf-8")


def test_firstboot_does_not_restart_ordered_service_from_inside_unit(tmp_path: Path) -> None:
    systemctl_log = tmp_path / "systemctl.log"
    fake_systemctl = tmp_path / "systemctl"
    fake_systemctl.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$WEB_SPECTROMETER_SYSTEMCTL_LOG\"\n",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)

    run_firstboot(
        tmp_path,
        "lab-spectrometer",
        str(fake_systemctl),
        {"WEB_SPECTROMETER_SYSTEMCTL_LOG": str(systemctl_log)},
    )

    calls = systemctl_log.read_text(encoding="utf-8").splitlines()
    assert "enable web-spectrometer.service" in calls
    assert "disable web-spectrometer-firstboot.service" in calls
    assert "start --no-block web-spectrometer.service" in calls
    assert all(not call.startswith("restart ") for call in calls)
