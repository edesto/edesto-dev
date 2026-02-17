# WiFi Endpoint Example

An ESP32 HTTP server that exposes a /health endpoint.

## Expected Behavior
- Connects to WiFi (configure SSID/password in config.h, copy from config.h.example)
- Runs HTTP server on port 80
- GET /health returns `{"status": "ok", "uptime": <millis>}` with Content-Type: application/json

## How to Validate
Run `python validate.py` after flashing. It reads serial to find the IP, then checks:
- /health returns status 200
- Content-Type is application/json
- Response body is valid JSON

## Known Issue
Users report the /health endpoint returns data but some HTTP clients don't parse it correctly as JSON.
