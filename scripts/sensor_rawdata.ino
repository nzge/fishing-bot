#include "HX711.h"

#define DT 3
#define SCK 2

HX711 scale;

void setup() {
  Serial.begin(9600);
  scale.begin(DT, SCK);

  Serial.println("HX711 raw stability test");
  delay(1000);
}

void loop() {
  if (scale.is_ready()) {
    long raw1 = scale.read();
    long avg5 = scale.read_average(5);
    long avg20 = scale.read_average(20);

    Serial.print("raw: ");
    Serial.print(raw1);

    Serial.print(" | avg5: ");
    Serial.print(avg5);

    Serial.print(" | avg20: ");
    Serial.println(avg20);
  } else {
    Serial.println("HX711 not ready");
  }

  delay(500);
}
