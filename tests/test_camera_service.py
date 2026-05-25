import unittest
from pathlib import Path
import tempfile

try:
    import httpx
except ImportError:  # pragma: no cover - optional local dependency
    httpx = None

from pi.camera_service import ServiceConfig, create_app
from spectrometer_core import ExtractionSettings


@unittest.skipIf(httpx is None, "httpx test dependency is not installed")
class CameraServiceTests(unittest.IsolatedAsyncioTestCase):
    def make_app(self):
        config = ServiceConfig(
            access_token="test-token",
            camera_backend="mock",
            settings=ExtractionSettings(frame_width=64, frame_height=48, output_width=64),
        )
        app = create_app(config=config)
        app.state.spectrometer.start()
        return app

    def make_client(self, app):
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def test_health_is_available_without_token(self):
        async with self.make_client(self.make_app()) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["camera"], "mock")
        self.assertTrue(response.json()["auth_required"])

    async def test_root_describes_api_without_token(self):
        async with self.make_client(self.make_app()) as client:
            response = await client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "web-spectrometer-device")
        self.assertEqual(response.json()["openapi"], "/openapi.json")

    async def test_settings_require_token(self):
        async with self.make_client(self.make_app()) as client:
            response = await client.get("/settings")
            authorized = await client.get("/settings", headers={"X-Spectrometer-Token": "test-token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(authorized.status_code, 200)

    async def test_patch_settings_changes_spectrum_extraction(self):
        async with self.make_client(self.make_app()) as client:
            response = await client.patch(
                "/settings",
                headers={"X-Spectrometer-Token": "test-token"},
                json={"row_center_y": 24, "half_height": 2, "angle_degrees": 5},
            )
            spectrum = await client.get("/spectrum", headers={"X-Spectrometer-Token": "test-token"})

        self.assertEqual(response.status_code, 200)
        settings = response.json()
        self.assertEqual(settings["row_center_y"], 24)
        self.assertEqual(settings["half_height"], 2)
        self.assertEqual(settings["angle_degrees"], 5)
        self.assertEqual(spectrum.status_code, 200)
        self.assertEqual(spectrum.headers["x-spectrum-width"], "64")
        self.assertEqual(spectrum.headers["x-spectrum-format"], "uint8")
        self.assertEqual(len(spectrum.content), 64)

    async def test_raw_frame_headers_include_shape(self):
        async with self.make_client(self.make_app()) as client:
            response = await client.get("/frame.raw", headers={"X-Spectrometer-Token": "test-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-frame-width"], "64")
        self.assertEqual(response.headers["x-frame-height"], "48")
        self.assertEqual(response.headers["x-frame-format"], "RGB888")
        self.assertEqual(len(response.content), 64 * 48 * 3)

    async def test_unpaired_device_can_be_paired_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                """
{
  "service": {
    "host": "0.0.0.0",
    "port": 8765,
    "access_token": "",
    "pairing_required": true,
    "camera_backend": "mock"
  },
  "settings": {
    "frame_width": 64,
    "frame_height": 48,
    "output_width": 64
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            app = create_app(config_path=str(config_path))
            app.state.spectrometer.start()

            async with self.make_client(app) as client:
                health = await client.get("/health")
                blocked = await client.get("/settings")
                paired = await client.post(
                    "/pairing",
                    json={"access_token": "new-secret", "friendly_name": "Bench"},
                )
                settings = await client.get("/settings", headers={"X-Spectrometer-Token": "new-secret"})
                pair_again = await client.post("/pairing", json={"access_token": "other-secret"})

            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["pairing_required"])
            self.assertFalse(health.json()["auth_required"])
            self.assertEqual(blocked.status_code, 428)
            self.assertEqual(paired.status_code, 200)
            self.assertEqual(settings.status_code, 200)
            self.assertEqual(pair_again.status_code, 409)

            updated = config_path.read_text(encoding="utf-8")
            self.assertIn('"access_token": "new-secret"', updated)
            self.assertIn('"pairing_required": false', updated)
            self.assertIn('"friendly_name": "Bench"', updated)

    async def test_missing_config_defaults_to_pairing_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "missing-config.json"
            app = create_app(config_path=str(config_path))
            app.state.spectrometer.start()

            async with self.make_client(app) as client:
                health = await client.get("/health")
                blocked = await client.get("/settings")

            self.assertEqual(health.status_code, 200)
            self.assertFalse(health.json()["auth_required"])
            self.assertTrue(health.json()["pairing_required"])
            self.assertEqual(blocked.status_code, 428)


if __name__ == "__main__":
    unittest.main()
