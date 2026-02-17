#include <WiFi.h>
#include <WebServer.h>
#include "config.h"

WebServer server(80);

void handleHealth() {
    String json = "{\"status\": \"ok\", \"uptime\": " + String(millis()) + "}";
    // BUG: wrong content type for JSON response
    server.send(200, "text/plain", json);
}

void setup() {
    Serial.begin(115200);

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WIFI] Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    Serial.println("[WIFI] IP:" + WiFi.localIP().toString());

    server.on("/health", handleHealth);
    server.begin();
    Serial.println("[HTTP] server started");
    Serial.println("[READY]");
}

void loop() {
    server.handleClient();
}
