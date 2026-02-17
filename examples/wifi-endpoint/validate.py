import serial
import time
import sys
import urllib.request
import json

PORT = "/dev/ttyUSB0"  # Update to match your port

# Read serial to find IP address
ser = serial.Serial(PORT, 115200, timeout=1)
time.sleep(5)

ip = None
start = time.time()
while time.time() - start < 15:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if "[WIFI] IP:" in line:
        ip = line.split("IP:")[-1].strip()
        break
ser.close()

if not ip:
    print("[FAIL] Could not find device IP address in serial output.")
    sys.exit(1)

print(f"[INFO] Device IP: {ip}")

# Check /health endpoint
try:
    req = urllib.request.Request(f"http://{ip}/health")
    response = urllib.request.urlopen(req, timeout=5)

    status = response.status
    content_type = response.headers.get("Content-Type", "")
    body = response.read().decode("utf-8")

    print(f"[INFO] Status: {status}")
    print(f"[INFO] Content-Type: {content_type}")
    print(f"[INFO] Body: {body}")

    passed = True

    if status != 200:
        print(f"[FAIL] Expected status 200, got {status}")
        passed = False

    if "application/json" not in content_type:
        print(f"[FAIL] Expected Content-Type 'application/json', got '{content_type}'")
        passed = False

    try:
        json.loads(body)
        print("[PASS] Body is valid JSON")
    except json.JSONDecodeError:
        print("[FAIL] Body is not valid JSON")
        passed = False

    if passed:
        print("\nAll checks passed.")
        sys.exit(0)
    else:
        print(f"\nSome checks failed.")
        sys.exit(1)

except Exception as e:
    print(f"[FAIL] Could not reach device: {e}")
    sys.exit(1)
