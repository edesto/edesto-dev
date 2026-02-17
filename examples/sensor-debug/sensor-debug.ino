// Temperature sensor simulation with conversion bug
// The Fahrenheit conversion has an intentional error for Claude Code to find

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("[READY]");
}

void loop() {
    // Simulate temperature reading (incrementing pattern)
    float celsius = 20.0 + (millis() / 10000.0);
    if (celsius > 40.0) celsius = 20.0 + fmod(celsius - 20.0, 20.0);

    // BUG: incorrect offset in conversion
    float fahrenheit = (celsius * 9.0 / 5.0) + 23;

    Serial.print("[SENSOR] celsius=");
    Serial.print(celsius, 1);
    Serial.print(" fahrenheit=");
    Serial.println(fahrenheit, 1);

    delay(2000);
}
