import serial
import time
import sys

PORT = "/dev/ttyUSB0"  # Update to match your port

ser = serial.Serial(PORT, 115200, timeout=1)
time.sleep(3)

results = []
start = time.time()
while time.time() - start < 15 and len(results) < 5:
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if "[SENSOR]" in line:
        parts = dict(p.split("=") for p in line.split("[SENSOR]")[1].strip().split())
        c = float(parts["celsius"])
        f = float(parts["fahrenheit"])
        expected_f = (c * 9 / 5) + 32
        passed = abs(f - expected_f) < 0.1
        results.append(passed)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] celsius={c} fahrenheit={f} expected={expected_f:.1f}")

ser.close()

if all(results) and len(results) >= 3:
    print("\nAll readings correct.")
    sys.exit(0)
else:
    print(f"\n{sum(results)}/{len(results)} readings correct.")
    sys.exit(1)
