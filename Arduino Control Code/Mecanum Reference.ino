/*
  Serial command format (newline-terminated):
    m x 50 y 0 r 30

  x = strafe left/right   (-100..100)
  y = forward/back        (-100..100)
  r = rotation            (-100..100)

  Mecanum mix (standard):
    FL = y + x + r
    FR = y - x - r
    RL = y - x + r
    RR = y + x - r

  DRV8833 1PWM+1DIR wiring per motor:
    PWM -> IN1
    DIR -> IN2

  Forward: DIR=LOW,  IN1=PWM (coast on PWM low)
  Reverse: DIR=HIGH, IN1=INV_PWM (brake on IN1 high, reverse on IN1 low)
*/

#include <Arduino.h>

// ---------- Pin mapping (example for Arduino Uno) ----------
// Choose 4 PWM-capable pins for PWM_*
// Uno PWM pins: 3,5,6,9,10,11

const uint8_t FL_PWM = 3;   // PWM -> FL IN1
const uint8_t FL_DIR = 2;   // DIR -> FL IN2 (any digital pin)

const uint8_t FR_PWM = 5;
const uint8_t FR_DIR = 4;

const uint8_t RL_PWM = 6;
const uint8_t RL_DIR = 7;

const uint8_t RR_PWM = 9;
const uint8_t RR_DIR = 8;

// Flip sign per motor if needed (+1 or -1)
const int8_t FL_SIGN = +1;
const int8_t FR_SIGN = +1;
const int8_t RL_SIGN = +1;
const int8_t RR_SIGN = +1;

const int DEADZONE = 3;     // input deadband in -100..100 units
const uint32_t BAUD = 115200;

// ---------- Serial line buffer ----------
static char lineBuf[80];
static size_t lineLen = 0;

// ---------- Helpers ----------
static int clamp100(int v) {
  if (v > 100) return 100;
  if (v < -100) return -100;
  return v;
}

static int applyDeadzone(int v) {
  return (abs(v) < DEADZONE) ? 0 : v;
}

// cmd100: -100..100
// Uses 1 PWM + 1 DIR pin on DRV8833 as described above.
static void setMotor_1PWM1DIR(uint8_t pwmPin, uint8_t dirPin, int cmd100) {
  cmd100 = clamp100(cmd100);

  if (cmd100 == 0) {
    // Coast stop: (0,0)
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, 0);
    return;
  }

  int pwm = (int)lround((abs(cmd100) * 255.0) / 100.0);

  if (cmd100 > 0) {
    // Forward: (PWM, 0) -> forward/coast
    digitalWrite(dirPin, LOW);
    analogWrite(pwmPin, pwm);
  } else {
    // Reverse with inverted PWM: (INV_PWM, 1) -> reverse/brake
    digitalWrite(dirPin, HIGH);
    analogWrite(pwmPin, 255 - pwm);
  }
}

static bool readLineFromSerial(char *out, size_t outSize) {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      strncpy(out, lineBuf, outSize);
      out[outSize - 1] = '\0';
      lineLen = 0;
      return true;
    }

    if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    }
  }
  return false;
}

static void processCommand(char *s) {
  // Expect: m x <int> y <int> r <int>
  char *tok = strtok(s, " ");
  if (!tok) return;
  if (!(tok[0] == 'm' || tok[0] == 'M')) return;

  int x = 0, y = 0, r = 0;

  while (true) {
    char *axis = strtok(nullptr, " ");
    if (!axis) break;
    char *valS = strtok(nullptr, " ");
    if (!valS) break;

    int v = atoi(valS);
    if (axis[0] == 'x' || axis[0] == 'X') x = v;
    else if (axis[0] == 'y' || axis[0] == 'Y') y = v;
    else if (axis[0] == 'r' || axis[0] == 'R') r = v;
  }

  x = applyDeadzone(clamp100(x));
  y = applyDeadzone(clamp100(y));
  r = applyDeadzone(clamp100(r));

  // Mecanum mixing
  float fl = (float)(y + x + r);
  float fr = (float)(y - x - r);
  float rl = (float)(y - x + r);
  float rr = (float)(y + x - r);

  // Normalize to keep within +/-100
  float maxMag = max(max(fabs(fl), fabs(fr)), max(fabs(rl), fabs(rr)));
  if (maxMag > 100.0f) {
    float scale = 100.0f / maxMag;
    fl *= scale; fr *= scale; rl *= scale; rr *= scale;
  }

  int flCmd = (int)lround(fl) * FL_SIGN;
  int frCmd = (int)lround(fr) * FR_SIGN;
  int rlCmd = (int)lround(rl) * RL_SIGN;
  int rrCmd = (int)lround(rr) * RR_SIGN;

  setMotor_1PWM1DIR(FL_PWM, FL_DIR, flCmd);
  setMotor_1PWM1DIR(FR_PWM, FR_DIR, frCmd);
  setMotor_1PWM1DIR(RL_PWM, RL_DIR, rlCmd);
  setMotor_1PWM1DIR(RR_PWM, RR_DIR, rrCmd);

  // Optional debug:
  // Serial.print("FL FR RL RR = ");
  // Serial.print(flCmd); Serial.print(" ");
  // Serial.print(frCmd); Serial.print(" ");
  // Serial.print(rlCmd); Serial.print(" ");
  // Serial.println(rrCmd);
}

void setup() {
  Serial.begin(BAUD);

  pinMode(FL_PWM, OUTPUT); pinMode(FL_DIR, OUTPUT);
  pinMode(FR_PWM, OUTPUT); pinMode(FR_DIR, OUTPUT);
  pinMode(RL_PWM, OUTPUT); pinMode(RL_DIR, OUTPUT);
  pinMode(RR_PWM, OUTPUT); pinMode(RR_DIR, OUTPUT);

  // Stop all
  setMotor_1PWM1DIR(FL_PWM, FL_DIR, 0);
  setMotor_1PWM1DIR(FR_PWM, FR_DIR, 0);
  setMotor_1PWM1DIR(RL_PWM, RL_DIR, 0);
  setMotor_1PWM1DIR(RR_PWM, RR_DIR, 0);

  Serial.println("Ready: send 'm x <int> y <int> r <int>'");
}

void loop() {
  char line[80];
  if (readLineFromSerial(line, sizeof(line))) {
    processCommand(line);
  }
}
