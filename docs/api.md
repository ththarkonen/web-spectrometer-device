# Device API Contract

The device exposes a local HTTP API. API responses are JSON unless the endpoint explicitly returns raw binary data.

Default base URL:

```text
http://<hostname-or-ip>:8765
```

## Authentication

Unpaired devices report `pairing_required: true` from `GET /health` and accept one `POST /pairing` request. Pairing stores the submitted access code on the device and disables pairing.

After pairing, use:

```http
X-Spectrometer-Token: <access-code>
```

For the WebSocket stream, pass the token in the query string:

```text
ws://<hostname-or-ip>:8765/stream?token=<access-code>
```

The token mechanism is intended for trusted local networks, not internet exposure.

The device enables CORS for configured origins. The default image uses `["*"]` so a separately hosted UI can call the API on the local network.

## Endpoints

### `GET /`

Unauthenticated API landing response:

```json
{
  "service": "web-spectrometer-device",
  "status": "ok",
  "health": "/health",
  "openapi": "/openapi.json",
  "docs": "/docs"
}
```

### `GET /health`

Unauthenticated device status:

```json
{
  "status": "ok",
  "camera": "picamera2",
  "auth_required": true,
  "pairing_required": false,
  "friendly_name": "Bench spectrometer",
  "frame": {
    "width": 800,
    "height": 600,
    "format": "RGB888"
  }
}
```

### `POST /pairing`

Allowed only while unpaired.

Request:

```json
{
  "access_token": "at-least-8-chars",
  "friendly_name": "Bench spectrometer"
}
```

Response:

```json
{
  "status": "paired",
  "auth_required": true,
  "pairing_required": false,
  "friendly_name": "Bench spectrometer"
}
```

### `GET /settings`

Requires token.

Response:

```json
{
  "frame_width": 800,
  "frame_height": 600,
  "output_width": 800,
  "row_center_y": 300.0,
  "half_height": 1,
  "angle_degrees": 0.0,
  "reverse_x": false,
  "gain": 1.0,
  "frame_duration_us": 40000
}
```

### `PATCH /settings`

Requires token. Partial updates are accepted.

Writable fields:

- `row_center_y`
- `half_height`
- `angle_degrees`
- `reverse_x`
- `gain`
- `frame_duration_us`

Frame shape fields are read-only at runtime.

Example:

```json
{
  "gain": 2.5,
  "row_center_y": 318,
  "half_height": 2
}
```

### `GET /frame.raw`

Requires token. Returns full frame bytes as `RGB888`.

Headers:

```text
X-Frame-Width: 800
X-Frame-Height: 600
X-Frame-Format: RGB888
Content-Type: application/octet-stream
```

Payload length is `width * height * 3` bytes.

### `GET /spectrum`

Requires token. Returns one extracted spectrum row as `uint8` bytes.

Headers:

```text
X-Spectrum-Width: 800
X-Spectrum-Format: uint8
X-Row-Center-Y: 300.0
X-Row-Half-Height: 1
X-Row-Angle-Degrees: 0.0
Content-Type: application/octet-stream
```

Payload length is `X-Spectrum-Width` bytes.

### `WS /stream`

Requires `token` query parameter. Sends repeated binary `uint8` spectra.

Query parameters:

- `token`: access code.
- `interval_ms`: requested interval, clamped by the device between 20 ms and 5000 ms.

Example:

```text
ws://spectrometer.local:8765/stream?token=<access-code>&interval_ms=100
```
