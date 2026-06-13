/*
 * HX711 load cell → USB serial for the ROS load_cell_node.
 *
 * Protocol (matches software/src/sensors/sensors/arduino_load_cell.py):
 *   raw: <integer>\n
 *
 * Wiring (Arduino Mega 2560): DT → pin 3, SCK → pin 2
 * Flash: firmware/scripts/flash.sh
 */
#include "HX711.h"

#define HX711_DT 3
#define HX711_SCK 2

// ~40 Hz matches ROS publish_rate; HX711 needs time per conversion.
static const unsigned long SAMPLE_PERIOD_MS = 25;
static const uint8_t AVERAGE_SAMPLES = 5;

HX711 scale;

void setup() {
  Serial.begin(9600);
  scale.begin(HX711_DT, HX711_SCK);
  scale.set_scale(1.0f);
  scale.tare(AVERAGE_SAMPLES);

  // Banner is ignored by the ROS parser (non-matching lines).
  Serial.println(F("load_cell firmware ready"));
  delay(500);
}

void loop() {
  static unsigned long last_ms = 0;
  unsigned long now = millis();
  if (now - last_ms < SAMPLE_PERIOD_MS) {
    return;
  }
  last_ms = now;

  if (!scale.is_ready()) {
    Serial.println(F("HX711 not ready"));
    return;
  }

  long raw = scale.read_average(AVERAGE_SAMPLES);
  Serial.print(F("raw: "));
  Serial.println(raw);
}
