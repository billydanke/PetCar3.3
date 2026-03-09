#include <Arduino.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/*
  PetCar3.3 mecanum drive controller

  Serial commands (newline terminated):
    m x <int> y <int> r <int>
    b query

  Example:
    m x 25 y 60 r -10

  Motor driver mode:
    Each DRV8833 motor channel uses one PWM pin plus one direction pin.
    Forward  = PWM duty on the PWM pin, direction pin LOW  (power/coast)
    Reverse  = inverse PWM on the PWM pin, direction HIGH  (power/brake)

  Battery input:
    A7 reads pack voltage through a 1:2 divider.
*/

namespace Config {
  constexpr unsigned long SERIAL_BAUD = 115200;
  constexpr size_t LINE_BUFFER_SIZE = 96;

  constexpr int INPUT_MIN = -100;
  constexpr int INPUT_MAX = 100;
  constexpr int INPUT_DEADZONE = 3;

  constexpr float ADC_REFERENCE_VOLTS = 5.0f; // Update this with the actual regulated voltage with the pi on.
  constexpr float BATTERY_DIVIDER_GAIN = 2.0f;
  constexpr int BATTERY_SAMPLES = 8;

  // Placeholder only until the WS2812B data pin is assigned.
  constexpr int LED_DATA_PIN = -1;

  // Front-left motor on left driver IN4/IN3.
  constexpr uint8_t FL_PWM_PIN = 9;
  constexpr uint8_t FL_DIR_PIN = 10;

  // Rear-left motor on left driver IN2/IN1.
  constexpr uint8_t RL_PWM_PIN = 11;
  constexpr uint8_t RL_DIR_PIN = 12;

  // Front-right motor on right driver IN4/IN3.
  constexpr uint8_t FR_PWM_PIN = 3;
  constexpr uint8_t FR_DIR_PIN = 4;

  // Rear-right motor on right driver IN2/IN1.
  constexpr uint8_t RR_PWM_PIN = 6;
  constexpr uint8_t RR_DIR_PIN = 7;

  constexpr uint8_t BATTERY_PIN = A7;

  // Adjust these after the first wheel-spin check if any wheel runs backwards.
  constexpr int8_t FL_SIGN = +1;
  constexpr int8_t FR_SIGN = +1;
  constexpr int8_t RL_SIGN = +1;
  constexpr int8_t RR_SIGN = +1;
}

struct DriveVector {
  int x = 0;
  int y = 0;
  int r = 0;
};

static char gLineBuffer[Config::LINE_BUFFER_SIZE];
static size_t gLineLength = 0;

static int clampPercent(int value) {
  if (value > Config::INPUT_MAX) {
    return Config::INPUT_MAX;
  }
  if (value < Config::INPUT_MIN) {
    return Config::INPUT_MIN;
  }
  return value;
}

static int applyDeadzone(int value) {
  return (abs(value) < Config::INPUT_DEADZONE) ? 0 : value;
}

static int percentToPwm(int percent) {
  percent = abs(percent);
  if (percent > 100) {
    percent = 100;
  }
  return (int)lroundf((percent * 255.0f) / 100.0f);
}

static void setMotor1Pwm1Dir(uint8_t pwmPin, uint8_t dirPin, int commandPercent) {
  commandPercent = clampPercent(commandPercent);

  if (commandPercent == 0) {
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, 0);
    return;
  }

  const int pwmValue = percentToPwm(commandPercent);

  if (commandPercent > 0) {
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, pwmValue);
    return;
  }

  digitalWrite(dirPin, HIGH);
  analogWrite(pwmPin, 255 - pwmValue);
}

static void stopAllMotors() {
  setMotor1Pwm1Dir(Config::FL_PWM_PIN, Config::FL_DIR_PIN, 0);
  setMotor1Pwm1Dir(Config::FR_PWM_PIN, Config::FR_DIR_PIN, 0);
  setMotor1Pwm1Dir(Config::RL_PWM_PIN, Config::RL_DIR_PIN, 0);
  setMotor1Pwm1Dir(Config::RR_PWM_PIN, Config::RR_DIR_PIN, 0);
}

static float readBatteryVoltage() {
  long sum = 0;
  for (int i = 0; i < Config::BATTERY_SAMPLES; ++1) {
    sum += analogRead(Config::BATTERY_PIN)
  }
  const float raw = (float)sum / Config::BATTERY_SAMPLES;
  const float sensedVoltage = (raw * Config::ADC_REFERENCE_VOLTS) / 1023.0f;
  return sensedVoltage * Config::BATTERY_DIVIDER_GAIN;
}

static void handleLedPlaceholder() {
  if (Config::LED_DATA_PIN >= 0) {
    pinMode((uint8_t)Config::LED_DATA_PIN, OUTPUT);
  }
}

static void driveMecanum(const DriveVector &drive) {
  float fl = (float)drive.y + (float)drive.x + (float)drive.r;
  float fr = (float)drive.y - (float)drive.x - (float)drive.r;
  float rl = (float)drive.y - (float)drive.x + (float)drive.r;
  float rr = (float)drive.y + (float)drive.x - (float)drive.r;

  const float maxMagnitude = max(
    max(fabsf(fl), fabsf(fr)),
    max(fabsf(rl), fabsf(rr))
  );

  if (maxMagnitude > 100.0f) {
    const float scale = 100.0f / maxMagnitude;
    fl *= scale;
    fr *= scale;
    rl *= scale;
    rr *= scale;
  }

  setMotor1Pwm1Dir(
    Config::FL_PWM_PIN,
    Config::FL_DIR_PIN,
    (int)lroundf(fl) * Config::FL_SIGN
  );
  setMotor1Pwm1Dir(
    Config::FR_PWM_PIN,
    Config::FR_DIR_PIN,
    (int)lroundf(fr) * Config::FR_SIGN
  );
  setMotor1Pwm1Dir(
    Config::RL_PWM_PIN,
    Config::RL_DIR_PIN,
    (int)lroundf(rl) * Config::RL_SIGN
  );
  setMotor1Pwm1Dir(
    Config::RR_PWM_PIN,
    Config::RR_DIR_PIN,
    (int)lroundf(rr) * Config::RR_SIGN
  );
}

static bool readSerialLine(char *outLine, size_t outSize) {
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      gLineBuffer[gLineLength] = '\0';
      strncpy(outLine, gLineBuffer, outSize);
      outLine[outSize - 1] = '\0';
      gLineLength = 0;
      return true;
    }

    if (gLineLength < (Config::LINE_BUFFER_SIZE - 1)) {
      gLineBuffer[gLineLength++] = c;
    }
  }

  return false;
}

static bool parseDriveVector(char *command, DriveVector &drive) {
  char *token = strtok(command, " ");
  if (token == nullptr || (token[0] != 'm' && token[0] != 'M')) {
    return false;
  }

  while (true) {
    char *key = strtok(nullptr, " ");
    if (key == nullptr) {
      break;
    }

    char *valueToken = strtok(nullptr, " ");
    if (valueToken == nullptr) {
      return false;
    }

    const int value = clampPercent(atoi(valueToken));

    switch (tolower(key[0])) {
      case 'x':
        drive.x = value;
        break;
      case 'y':
        drive.y = value;
        break;
      case 'r':
        drive.r = value;
        break;
      default:
        break;
    }
  }

  drive.x = applyDeadzone(drive.x);
  drive.y = applyDeadzone(drive.y);
  drive.r = applyDeadzone(drive.r);
  return true;
}

static void respondBatteryQuery() {
  const float voltage = readBatteryVoltage();
  Serial.print("b ");
  Serial.println(voltage, 3);
}

static bool isBatteryQuery(const char *argument) {
  if (argument == nullptr) {
    return true;
  }

  return
    tolower(argument[0]) == 'q' &&
    (
      argument[1] == '\0' ||
      (
        tolower(argument[1]) == 'u' &&
        tolower(argument[2]) == 'e' &&
        tolower(argument[3]) == 'r' &&
        tolower(argument[4]) == 'y' &&
        argument[5] == '\0'
      )
    );
}

static void processCommand(char *commandLine) {
  if (commandLine[0] == '\0') {
    return;
  }

  char commandCopy[Config::LINE_BUFFER_SIZE];
  strncpy(commandCopy, commandLine, sizeof(commandCopy));
  commandCopy[sizeof(commandCopy) - 1] = '\0';

  char *command = strtok(commandCopy, " ");
  if (command == nullptr) {
    return;
  }

  switch (tolower(command[0])) {
    case 'm': {
      DriveVector drive;
      if (parseDriveVector(commandLine, drive)) {
        driveMecanum(drive);
      }
      break;
    }

    case 'b': {
      char *argument = strtok(nullptr, " ");
      if (isBatteryQuery(argument)) {
        respondBatteryQuery();
      }
      break;
    }

    default:
      break;
  }
}

void setup() {
  Serial.begin(Config::SERIAL_BAUD);

  pinMode(Config::FL_PWM_PIN, OUTPUT);
  pinMode(Config::FL_DIR_PIN, OUTPUT);
  pinMode(Config::FR_PWM_PIN, OUTPUT);
  pinMode(Config::FR_DIR_PIN, OUTPUT);
  pinMode(Config::RL_PWM_PIN, OUTPUT);
  pinMode(Config::RL_DIR_PIN, OUTPUT);
  pinMode(Config::RR_PWM_PIN, OUTPUT);
  pinMode(Config::RR_DIR_PIN, OUTPUT);
  pinMode(Config::BATTERY_PIN, INPUT);

  stopAllMotors();
  handleLedPlaceholder();
}

void loop() {
  char commandLine[Config::LINE_BUFFER_SIZE];
  if (readSerialLine(commandLine, sizeof(commandLine))) {
    processCommand(commandLine);
  }
}
