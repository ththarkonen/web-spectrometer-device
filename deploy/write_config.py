from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: write_config.py CONFIG_PATH ACCESS_TOKEN [PAIRING_REQUIRED]")

    path = Path(sys.argv[1])
    token = sys.argv[2]
    pairing_required = False
    if len(sys.argv) == 4:
        pairing_required = sys.argv[3].lower() in {"1", "true", "yes"}
    data = {
        "service": {
            "host": "0.0.0.0",
            "port": 8765,
            "access_token": token,
            "pairing_required": pairing_required,
            "camera_backend": "auto",
            "cors_origins": ["*"],
        },
        "settings": {
            "frame_width": 800,
            "frame_height": 600,
            "output_width": 800,
            "row_center_y": 300,
            "half_height": 1,
            "angle_degrees": 0,
            "reverse_x": False,
            "gain": 1.0,
            "frame_duration_us": 40000,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
