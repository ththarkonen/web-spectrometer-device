from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class ExtractionSettings:
    frame_width: int = 800
    frame_height: int = 600
    output_width: int = 800
    row_center_y: float = 300.0
    half_height: int = 1
    angle_degrees: float = 0.0
    reverse_x: bool = False
    gain: float = 1.0
    frame_duration_us: int = 40000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_NUMERIC_FIELDS = {
    "frame_width": int,
    "frame_height": int,
    "output_width": int,
    "row_center_y": float,
    "half_height": int,
    "angle_degrees": float,
    "gain": float,
    "frame_duration_us": int,
}


def update_settings(
    settings: ExtractionSettings,
    updates: Mapping[str, Any],
) -> ExtractionSettings:
    """Return settings with validated updates applied."""

    values = settings.to_dict()

    for key, value in updates.items():
        if key == "reverse_x":
            values[key] = bool(value)
        elif key in _NUMERIC_FIELDS:
            values[key] = _NUMERIC_FIELDS[key](value)

    values["frame_width"] = max(1, values["frame_width"])
    values["frame_height"] = max(1, values["frame_height"])
    values["output_width"] = max(1, values["output_width"])
    values["half_height"] = max(0, values["half_height"])
    values["row_center_y"] = min(
        max(0.0, values["row_center_y"]),
        float(values["frame_height"] - 1),
    )
    values["angle_degrees"] = min(max(-45.0, values["angle_degrees"]), 45.0)
    values["gain"] = min(max(1.0, values["gain"]), 32.0)
    values["frame_duration_us"] = min(max(1000, values["frame_duration_us"]), 1000000)

    return ExtractionSettings(**values)


def frame_to_grayscale(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame)

    if image.ndim == 2:
        return image.astype(np.float32, copy=False)

    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("frame must be a grayscale or RGB image")

    rgb = image[..., :3].astype(np.float32, copy=False)
    return (0.299 * rgb[..., 0]) + (0.587 * rgb[..., 1]) + (0.114 * rgb[..., 2])


def spectrum_from_frame(
    frame: np.ndarray,
    settings: ExtractionSettings,
) -> np.ndarray:
    """Extract an averaged, optionally rotated spectrum row from an RGB frame."""

    gray = frame_to_grayscale(frame)
    frame_height, frame_width = gray.shape
    output_width = int(settings.output_width)

    if output_width < 1:
        raise ValueError("output_width must be positive")

    theta = math.radians(float(settings.angle_degrees))
    slope = math.tan(theta)
    normal_x = -math.sin(theta)
    normal_y = math.cos(theta)

    xs = np.linspace(0, frame_width - 1, output_width, dtype=np.float32)
    center_x = (frame_width - 1) / 2.0
    base_y = float(settings.row_center_y) + slope * (xs - center_x)
    offsets = np.arange(-settings.half_height, settings.half_height + 1, dtype=np.float32)

    rows = []
    for offset in offsets:
        sample_x = np.rint(xs + normal_x * offset).astype(np.int32)
        sample_y = np.rint(base_y + normal_y * offset).astype(np.int32)
        sample_x = np.clip(sample_x, 0, frame_width - 1)
        sample_y = np.clip(sample_y, 0, frame_height - 1)
        rows.append(gray[sample_y, sample_x])

    averaged = np.mean(np.stack(rows, axis=0), axis=0)
    if settings.reverse_x:
        averaged = averaged[::-1]

    return np.clip(np.rint(averaged), 0, 255).astype(np.uint8)
