#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include "config.h"

#define VERSION "1.0.0"

WebServer server(80);

void handleVersion() {
    server.send(200, "text/plain", VERSION);
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

    ArduinoOTA.setHostname("edesto-ota-demo");
    ArduinoOTA.begin();
    Serial.println("[OTA] ready");

    server.on("/version", handleVersion);
    server.begin();

    Serial.println("[OTA] version=" + String(VERSION));
    Serial.println("[READY]");
}

void loop() {
    ArduinoOTA.handle();
    server.handleClient();
}
