from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any, Mapping

import numpy as np

from spectrometer_core import ExtractionSettings, spectrum_from_frame, update_settings

try:
    from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - import error is clearer in main()
    Body = Depends = FastAPI = HTTPException = Query = Request = Response = WebSocket = WebSocketDisconnect = None
    CORSMiddleware = None


CONFIG_ENV = "SPECTROMETER_CONFIG"
TOKEN_ENV = "SPECTROMETER_TOKEN"
DEFAULT_CONFIG_PATH = "/etc/web-spectrometer/config.json"
READ_ONLY_HTTP_SETTINGS = {"frame_width", "frame_height", "output_width"}


@dataclass(frozen=True)
class ServiceConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    access_token: str | None = None
    pairing_required: bool = False
    friendly_name: str | None = None
    config_path: str | None = None
    camera_backend: str = "auto"
    cors_origins: tuple[str, ...] = ("*",)
    settings: ExtractionSettings = field(default_factory=ExtractionSettings)


class CameraBackend:
    name = "base"

    def start(self) -> None:
        raise NotImplementedError

    def capture_array(self) -> np.ndarray:
        raise NotImplementedError

    def apply_settings(self, settings: ExtractionSettings) -> None:
        pass


class PicameraBackend(CameraBackend):
    name = "picamera2"

    def __init__(self, settings: ExtractionSettings):
        self.settings = settings
        self.camera = None

    def start(self) -> None:
        from picamera2 import Picamera2

        self.camera = Picamera2()
        video_config = self.camera.create_video_configuration(
            main={
                "format": "RGB888",
                "size": (self.settings.frame_width, self.settings.frame_height),
            },
            controls={
                "FrameDurationLimits": (
                    self.settings.frame_duration_us,
                    self.settings.frame_duration_us,
                ),
                "AnalogueGain": float(self.settings.gain),
            },
        )
        self.camera.configure(video_config)
        self.camera.start()

    def capture_array(self) -> np.ndarray:
        if self.camera is None:
            raise RuntimeError("camera has not started")
        return self.camera.capture_array()

    def apply_settings(self, settings: ExtractionSettings) -> None:
        self.settings = settings
        if self.camera is None:
            return

        self.camera.set_controls(
            {
                "AnalogueGain": float(settings.gain),
                "FrameDurationLimits": (
                    int(settings.frame_duration_us),
                    int(settings.frame_duration_us),
                ),
            }
        )


class MockCameraBackend(CameraBackend):
    name = "mock"

    def __init__(self, settings: ExtractionSettings):
        self.settings = settings
        self.started = False

    def start(self) -> None:
        self.started = True

    def apply_settings(self, settings: ExtractionSettings) -> None:
        self.settings = settings

    def capture_array(self) -> np.ndarray:
        if not self.started:
            raise RuntimeError("mock camera has not started")

        width = self.settings.frame_width
        height = self.settings.frame_height
        x = np.linspace(0.0, 1.0, width, dtype=np.float32)
        y = np.arange(height, dtype=np.float32)[:, None]
        center = self.settings.row_center_y
        band = np.exp(-((y - center) ** 2) / (2.0 * 26.0**2))
        phase = time.time() * 0.3

        peaks = (
            0.9 * np.exp(-((x - 0.22) ** 2) / 0.0008)
            + 1.0 * np.exp(-((x - (0.48 + 0.03 * np.sin(phase))) ** 2) / 0.0018)
            + 0.7 * np.exp(-((x - 0.73) ** 2) / 0.0012)
        )
        baseline = 0.18 + 0.12 * np.sin(2.0 * np.pi * (x + phase * 0.1))
        intensity = np.clip(baseline + peaks, 0.0, 1.0)[None, :] * band

        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[..., 0] = np.clip(35 + 180 * intensity * x[None, :], 0, 255)
        frame[..., 1] = np.clip(28 + 210 * intensity, 0, 255)
        frame[..., 2] = np.clip(45 + 180 * intensity * (1.0 - x[None, :]), 0, 255)
        return frame


class ServiceState:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.settings = config.settings
        self.camera = self._create_camera(config.camera_backend)
        self.lock = threading.Lock()

    def _create_camera(self, backend_name: str) -> CameraBackend:
        if backend_name == "mock":
            return MockCameraBackend(self.settings)
        if backend_name == "picamera2":
            return PicameraBackend(self.settings)
        if backend_name != "auto":
            raise ValueError(f"unknown camera backend: {backend_name}")

        try:
            return PicameraBackend(self.settings)
        except Exception:
            return MockCameraBackend(self.settings)

    def start(self) -> None:
        try:
            self.camera.start()
        except Exception:
            if self.config.camera_backend == "auto" and self.camera.name != "mock":
                self.camera = MockCameraBackend(self.settings)
                self.camera.start()
                return
            raise

    def is_authorized(self, token: str | None) -> bool:
        if self.config.pairing_required and not self.config.access_token:
            return False
        if not self.config.access_token:
            return True
        return secrets.compare_digest(str(token or ""), self.config.access_token)

    def complete_pairing(self, access_token: str, friendly_name: str | None = None) -> dict[str, Any]:
        token = str(access_token or "").strip()
        if len(token) < 8:
            raise ValueError("access code must be at least 8 characters")
        if len(token) > 128:
            raise ValueError("access code must be at most 128 characters")
        if any(char.isspace() for char in token):
            raise ValueError("access code cannot contain whitespace")
        if self.config.access_token or not self.config.pairing_required:
            raise RuntimeError("spectrometer is already paired")

        name = str(friendly_name or "").strip() or None
        if name and len(name) > 80:
            raise ValueError("friendly name must be at most 80 characters")

        with self.lock:
            self._persist_pairing(token, name)
            self.config = replace(
                self.config,
                access_token=token,
                pairing_required=False,
                friendly_name=name or self.config.friendly_name,
            )

        return {
            "status": "paired",
            "auth_required": True,
            "pairing_required": False,
            "friendly_name": self.config.friendly_name,
        }

    def _persist_pairing(self, token: str, friendly_name: str | None) -> None:
        if not self.config.config_path:
            raise RuntimeError("cannot persist access code without a config path")

        path = Path(self.config.config_path)
        data: dict[str, Any] = {}
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)

        service_data = data.setdefault("service", {})
        if not isinstance(service_data, dict):
            service_data = {}
            data["service"] = service_data
        service_data["access_token"] = token
        service_data["pairing_required"] = False
        if friendly_name:
            service_data["friendly_name"] = friendly_name

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        try:
            tmp_path.chmod(path.stat().st_mode & 0o777)
        except FileNotFoundError:
            tmp_path.chmod(0o600)
        tmp_path.replace(path)

    def capture_frame(self) -> np.ndarray:
        with self.lock:
            return self.camera.capture_array()

    def capture_spectrum(self) -> tuple[np.ndarray, ExtractionSettings]:
        with self.lock:
            frame = self.camera.capture_array()
            settings = self.settings
        return spectrum_from_frame(frame, settings), settings

    def update(self, updates: Mapping[str, Any]) -> ExtractionSettings:
        if "settings" in updates and isinstance(updates["settings"], Mapping):
            updates = updates["settings"]

        read_only = sorted(READ_ONLY_HTTP_SETTINGS.intersection(updates.keys()))
        if read_only:
            fields = ", ".join(read_only)
            raise ValueError(f"settings are read-only at runtime: {fields}")

        with self.lock:
            new_settings = update_settings(self.settings, updates)
            self.settings = new_settings
            self.camera.apply_settings(new_settings)
            return new_settings


def load_config(config_path: str | None = None) -> ServiceConfig:
    path = Path(config_path or os.environ.get(CONFIG_ENV, DEFAULT_CONFIG_PATH))
    data: dict[str, Any] = {}
    config_exists = path.exists()
    if config_exists:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

    service_data = data.get("service", data)
    settings_data = data.get("settings", {})
    settings = update_settings(ExtractionSettings(), settings_data)

    token = os.environ.get(TOKEN_ENV) or service_data.get("access_token")
    if token == "":
        token = None
    allow_no_token = os.environ.get("SPECTROMETER_ALLOW_NO_TOKEN") == "1"
    generate_temporary_token = os.environ.get("SPECTROMETER_GENERATE_TEMP_TOKEN") == "1"
    pairing_required = False
    if token is None and not allow_no_token and generate_temporary_token:
        token = secrets.token_urlsafe(9)
        print(f"Generated temporary spectrometer token: {token}", flush=True)
    elif token is None and not allow_no_token:
        pairing_required = True

    cors_origins = service_data.get("cors_origins", ["*"])
    return ServiceConfig(
        host=str(service_data.get("host", "0.0.0.0")),
        port=int(service_data.get("port", 8765)),
        access_token=token,
        pairing_required=pairing_required,
        friendly_name=service_data.get("friendly_name") or None,
        config_path=str(path),
        camera_backend=str(service_data.get("camera_backend", "auto")),
        cors_origins=tuple(str(origin) for origin in cors_origins),
        settings=settings,
    )


def create_app(
    config_path: str | None = None,
    config: ServiceConfig | None = None,
) -> FastAPI:
    if FastAPI is None:
        raise RuntimeError("fastapi is required to run the Pi camera service")

    service_config = config or load_config(config_path)
    state = ServiceState(service_config)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.start()
        yield

    app = FastAPI(
        title="Web Spectrometer Device API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.spectrometer = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(service_config.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Frame-Width",
            "X-Frame-Height",
            "X-Frame-Format",
            "X-Spectrum-Width",
            "X-Spectrum-Format",
            "X-Row-Center-Y",
            "X-Row-Half-Height",
            "X-Row-Angle-Degrees",
        ],
        allow_credentials=False,
    )

    async def require_auth(request: Request, token: str | None = Query(default=None)) -> None:
        if state.config.pairing_required and not state.config.access_token:
            raise HTTPException(status_code=428, detail="spectrometer setup required")
        supplied_token = request.headers.get("x-spectrometer-token") or token
        if not state.is_authorized(supplied_token):
            raise HTTPException(status_code=401, detail="invalid spectrometer token")

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "service": "web-spectrometer-device",
            "status": "ok",
            "health": "/health",
            "openapi": "/openapi.json",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "camera": state.camera.name,
            "auth_required": bool(state.config.access_token),
            "pairing_required": bool(state.config.pairing_required and not state.config.access_token),
            "friendly_name": state.config.friendly_name,
            "frame": {
                "width": state.settings.frame_width,
                "height": state.settings.frame_height,
                "format": "RGB888",
            },
        }

    @app.get("/settings")
    async def get_settings(_: None = Depends(require_auth)) -> dict[str, Any]:
        return state.settings.to_dict()

    @app.patch("/settings")
    async def patch_settings(
        updates: dict[str, Any] = Body(...),
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        try:
            return state.update(updates).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/pairing")
    async def pairing(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return state.complete_pairing(
                access_token=str(payload.get("access_token") or payload.get("token") or ""),
                friendly_name=payload.get("friendly_name"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 409 if "already paired" in detail else 500
            raise HTTPException(status_code=status_code, detail=detail) from exc

    @app.get("/frame.raw")
    async def frame_raw(_: None = Depends(require_auth)) -> Response:
        frame = state.capture_frame()
        headers = {
            "X-Frame-Width": str(frame.shape[1]),
            "X-Frame-Height": str(frame.shape[0]),
            "X-Frame-Format": "RGB888",
        }
        return Response(frame[..., :3].tobytes(), media_type="application/octet-stream", headers=headers)

    @app.get("/spectrum")
    async def spectrum(
        _: None = Depends(require_auth),
    ) -> Response:
        values, settings = state.capture_spectrum()
        headers = {
            "X-Spectrum-Width": str(len(values)),
            "X-Spectrum-Format": "uint8",
            "X-Row-Center-Y": str(settings.row_center_y),
            "X-Row-Half-Height": str(settings.half_height),
            "X-Row-Angle-Degrees": str(settings.angle_degrees),
        }
        return Response(values.tobytes(), media_type="application/octet-stream", headers=headers)

    @app.websocket("/stream")
    async def stream(
        websocket: WebSocket,
        token: str | None = Query(default=None),
        interval_ms: int = Query(default=100),
    ) -> None:
        if not state.is_authorized(token):
            await websocket.close(code=1008)
            return

        await websocket.accept()
        interval = max(0.02, min(float(interval_ms) / 1000.0, 5.0))
        try:
            while True:
                values, _ = state.capture_spectrum()
                await websocket.send_bytes(values.tobytes())
                await asyncio.sleep(interval)
        except WebSocketDisconnect:
            return

    return app


def app() -> FastAPI:
    """ASGI factory for `uvicorn pi.camera_service:app --factory`."""

    return create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Raspberry Pi spectrometer camera API.")
    parser.add_argument("--config", default=None, help=f"Config file path. Defaults to ${CONFIG_ENV} or {DEFAULT_CONFIG_PATH}.")
    parser.add_argument("--host", default=None, help="Host/IP to bind.")
    parser.add_argument("--port", type=int, default=None, help="Port to bind.")
    parser.add_argument("--mock-camera", action="store_true", help="Use a synthetic camera feed.")
    args = parser.parse_args()

    import uvicorn

    config = load_config(args.config)
    if args.mock_camera:
        config = ServiceConfig(
            host=config.host,
            port=config.port,
            access_token=config.access_token,
            pairing_required=config.pairing_required,
            friendly_name=config.friendly_name,
            config_path=config.config_path,
            camera_backend="mock",
            cors_origins=config.cors_origins,
            settings=config.settings,
        )

    host = args.host or config.host
    port = args.port or config.port
    uvicorn.run(create_app(config=config), host=host, port=port)


if __name__ == "__main__":
    main()
