/*
 * Embedded Practical Exam - Part 1
 * Temperature reading, 16x2 LCD display, and serial transmission to PC.
 *
 * Temperature sensor (3-pin: S, +, -):
 *   S  -> A0  (digital data for DHT11, or analog for LM35/TMP36)
 *   +  -> D8  (power, acts as 5V)
 *   -  -> GND
 *
 * LCD (4-wire I2C): VCC->5V, GND->GND, SDA->A4, SCL->A5
 */

#define LCD_MODE_I2C      1
#define LCD_MODE_PARALLEL 0
#define LCD_MODE          LCD_MODE_I2C
#define I2C_LCD_ADDRESS   0x27

#define LCD_RS  12
#define LCD_EN  11
#define LCD_D4  5
#define LCD_D5  4
#define LCD_D6  3
#define LCD_D7  2

const char CANDIDATE_NAME[] = "Landra";

// ----- Pick sensor type -----
// DHT11: most common 3-pin module labeled S, +, - (fixes ~499 C on analog read)
#define SENSOR_ANALOG_LM35  1
#define SENSOR_ANALOG_TMP36 2
#define SENSOR_DHT11        3
#define SENSOR_TYPE         SENSOR_DHT11

#define SENSOR_VCC_PIN      8
#define SENSOR_SIGNAL_PIN   A0   // S wire stays on A0

const int LCD_COLS = 16;
const int LCD_ROWS = 2;
const unsigned long TEMP_READ_INTERVAL_MS = 2000;  // DHT11 needs >= 2 s
const unsigned long SCROLL_INTERVAL_MS = 300;

unsigned long lastTempReadMs = 0;
unsigned long lastScrollMs = 0;
int scrollIndex = 0;
String nameForScroll;
int scrollWidth = 0;

#if LCD_MODE == LCD_MODE_I2C
  #include <Wire.h>
  #include <LiquidCrystal_I2C.h>
  LiquidCrystal_I2C lcd(I2C_LCD_ADDRESS, LCD_COLS, LCD_ROWS);
#else
  #include <LiquidCrystal.h>
  LiquidCrystal lcd(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, LCD_D7);
#endif

#if SENSOR_TYPE == SENSOR_DHT11
  #include <DHT.h>
  DHT dht(SENSOR_SIGNAL_PIN, DHT11);
#endif

void initLcd() {
#if LCD_MODE == LCD_MODE_I2C
  Wire.begin();
  lcd.init();
  lcd.backlight();
#else
  lcd.begin(LCD_COLS, LCD_ROWS);
#endif
  lcd.display();
  lcd.clear();
}

void powerSensorOn() {
  pinMode(SENSOR_VCC_PIN, OUTPUT);
  digitalWrite(SENSOR_VCC_PIN, HIGH);
  delay(1000);  // let DHT11 stabilize after power-on
}

float readTemperatureC() {
#if SENSOR_TYPE == SENSOR_DHT11
  float t = dht.readTemperature();
  if (isnan(t)) {
    return 0.0;
  }
  return t;
#else
  long total = 0;
  for (int i = 0; i < 5; i++) {
    total += analogRead(SENSOR_SIGNAL_PIN);
    delay(10);
  }
  int raw = total / 5;
  float voltage = raw * (5.0 / 1024.0);

#if SENSOR_TYPE == SENSOR_ANALOG_TMP36
  return (voltage - 0.5) * 100.0;
#else
  return voltage * 100.0;
#endif
#endif
}

void prepareScrollText() {
  nameForScroll = String(CANDIDATE_NAME);
  if (nameForScroll.length() <= LCD_COLS) {
    scrollWidth = 0;
    return;
  }
  nameForScroll += "    ";
  scrollWidth = nameForScroll.length();
}

void showNameRow() {
  lcd.setCursor(0, 0);
  if (scrollWidth == 0) {
    lcd.print(CANDIDATE_NAME);
    int padding = LCD_COLS - strlen(CANDIDATE_NAME);
    for (int i = 0; i < padding; i++) {
      lcd.print(' ');
    }
    return;
  }
  for (int col = 0; col < LCD_COLS; col++) {
    int idx = (scrollIndex + col) % scrollWidth;
    lcd.print(nameForScroll.charAt(idx));
  }
  unsigned long now = millis();
  if (now - lastScrollMs >= SCROLL_INTERVAL_MS) {
    lastScrollMs = now;
    scrollIndex = (scrollIndex + 1) % scrollWidth;
  }
}

void showTemperatureRow(float temperatureC) {
  lcd.setCursor(0, 1);
  lcd.print("Temp: ");
  lcd.print(temperatureC, 1);
  lcd.print(" C  ");
}

void sendTemperatureToPc(float temperatureC) {
  Serial.print("TEMP:");
  Serial.println(temperatureC, 2);
}

void setup() {
  Serial.begin(9600);
  delay(500);

  powerSensorOn();

#if SENSOR_TYPE == SENSOR_DHT11
  dht.begin();
#endif

  initLcd();
  prepareScrollText();

  lcd.setCursor(0, 0);
  lcd.print("LCD Ready");
  lcd.setCursor(0, 1);
  lcd.print("DHT11 sensor");
  delay(1500);
  lcd.clear();
}

void loop() {
  showNameRow();

  unsigned long now = millis();
  if (now - lastTempReadMs >= TEMP_READ_INTERVAL_MS) {
    lastTempReadMs = now;
    float temperatureC = readTemperatureC();
    showTemperatureRow(temperatureC);
    sendTemperatureToPc(temperatureC);
  }
}
