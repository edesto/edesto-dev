# OTA Update Example

An ESP32 with Over-The-Air update support. Change the version string and push wirelessly.

## Expected Behavior
- Connects to WiFi (configure SSID/password in config.h)
- Enables ArduinoOTA for wireless firmware updates
- Prints `[OTA] version=1.0.0` to serial
- GET /version returns current version string

## How to Validate
Run `python validate.py` after flashing. It reads the version from serial output.
After an OTA update, run validate.py again to verify the version changed.

## Task
Update the VERSION string to "1.1.0" and push the update via OTA.
