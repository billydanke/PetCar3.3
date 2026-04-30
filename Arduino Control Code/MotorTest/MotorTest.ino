#include <Arduino.h>
#include <math.h>

namespace Config {
  constexpr uint8_t FL_PWM_PIN = 9;
  constexpr uint8_t FL_DIR_PIN = 10;

  constexpr uint8_t RL_PWM_PIN = 11;
  constexpr uint8_t RL_DIR_PIN = 12;

  constexpr uint8_t FR_PWM_PIN = 3;
  constexpr uint8_t FR_DIR_PIN = 4;

  constexpr uint8_t RR_PWM_PIN = 6;
  constexpr uint8_t RR_DIR_PIN = 7;

  constexpr int8_t FL_SIGN = -1;
  constexpr int8_t FR_SIGN = -1;
  constexpr int8_t RL_SIGN = +1;
  constexpr int8_t RR_SIGN = +1;

  constexpr int TEST_POWER = 45;
  constexpr unsigned long TEST_TIME_MS = 2000;
  constexpr unsigned long STOP_TIME_MS = 1000;
}

struct DriveVector {
  int x;
  int y;
  int r;
};

static int percentToPwm(int percent) {
  percent = abs(percent);
  if (percent > 100) percent = 100;
  return (int)lroundf((percent * 255.0f) / 100.0f);
}

static void setMotor(uint8_t pwmPin, uint8_t dirPin, int commandPercent) {
  if (commandPercent == 0) {
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, 0);
    return;
  }

  int pwmValue = percentToPwm(commandPercent);

  if (commandPercent > 0) {
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, pwmValue);
  } else {
    digitalWrite(dirPin, HIGH);
    analogWrite(pwmPin, 255 - pwmValue);
  }
}

static void stopAllMotors() {
  setMotor(Config::FL_PWM_PIN, Config::FL_DIR_PIN, 0);
  setMotor(Config::FR_PWM_PIN, Config::FR_DIR_PIN, 0);
  setMotor(Config::RL_PWM_PIN, Config::RL_DIR_PIN, 0);
  setMotor(Config::RR_PWM_PIN, Config::RR_DIR_PIN, 0);
}

static void driveMecanum(const DriveVector &drive) {
  float fl = drive.y + drive.x + drive.r;
  float fr = drive.y - drive.x - drive.r;
  float rl = drive.y - drive.x + drive.r;
  float rr = drive.y + drive.x - drive.r;

  float maxMagnitude = max(max(fabsf(fl), fabsf(fr)), max(fabsf(rl), fabsf(rr)));

  if (maxMagnitude > 100.0f) {
    float scale = 100.0f / maxMagnitude;
    fl *= scale;
    fr *= scale;
    rl *= scale;
    rr *= scale;
  }

  setMotor(Config::FL_PWM_PIN, Config::FL_DIR_PIN, (int)lroundf(fl) * Config::FL_SIGN);
  setMotor(Config::FR_PWM_PIN, Config::FR_DIR_PIN, (int)lroundf(fr) * Config::FR_SIGN);
  setMotor(Config::RL_PWM_PIN, Config::RL_DIR_PIN, (int)lroundf(rl) * Config::RL_SIGN);
  setMotor(Config::RR_PWM_PIN, Config::RR_DIR_PIN, (int)lroundf(rr) * Config::RR_SIGN);
}

static void runTest(const char *name, DriveVector drive) {
  Serial.println(name);
  driveMecanum(drive);
  delay(Config::TEST_TIME_MS);

  stopAllMotors();
  delay(Config::STOP_TIME_MS);
}

void setup() {
  Serial.begin(19200);

  pinMode(Config::FL_PWM_PIN, OUTPUT);
  pinMode(Config::FL_DIR_PIN, OUTPUT);
  pinMode(Config::FR_PWM_PIN, OUTPUT);
  pinMode(Config::FR_DIR_PIN, OUTPUT);
  pinMode(Config::RL_PWM_PIN, OUTPUT);
  pinMode(Config::RL_DIR_PIN, OUTPUT);
  pinMode(Config::RR_PWM_PIN, OUTPUT);
  pinMode(Config::RR_DIR_PIN, OUTPUT);

  stopAllMotors();
}

void loop() {
  const int p = Config::TEST_POWER;

  runTest("forward",        { 0,  p,  0 });
  runTest("backward",       { 0, -p,  0 });
  runTest("translate left", { -p, 0,  0 });
  runTest("translate right",{  p, 0,  0 });
  runTest("rotate left",    { 0,  0, -p });
  runTest("rotate right",   { 0,  0,  p });
}