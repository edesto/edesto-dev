import serial
import time
import sys

PORT = "/dev/ttyUSB0"  # Update to match your port

ser = serial.Serial(PORT, 115200, timeout=1)
time.sleep(5)

version = None
start = time.time()
while time.time() - start < 15:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if "[OTA] version=" in line:
        version = line.split("version=")[-1].strip()
        break
ser.close()

if not version:
    print("[FAIL] Could not read version from serial output.")
    sys.exit(1)

print(f"[INFO] Current version: {version}")
print("[PASS] Version string found.")
sys.exit(0)
