/*
  Arduino Nano base controller for tracked SLAM robot.

  Hardware assumptions:
    - Arduino Nano clone, likely ATmega328P + CH340C, 5 V logic.
    - HW-354 / MX1508 dual motor controller.
    - Two DC gear motors with hall/encoder signals S1/S2.
    - Raspberry Pi talks to this firmware over USB serial.

  Serial protocol, first version:
    Pi -> Arduino:
      V <left_ticks_per_sec> <right_ticks_per_sec>\n
      S\n
      ?\n
      Z\n      # zero encoder counts, useful during bench testing
      R\n      # report raw encoder pin levels and transition counts, useful during pinout testing

    Arduino -> Pi, periodic:
      E <millis> <left_position> <right_position> <left_tps> <right_tps> <left_pwm> <right_pwm>\n
      R <millis> <left_s1> <left_s2> <right_s1> <right_s2> <left_s1_edges> <left_s2_edges> <right_s1_edges> <right_s2_edges>\n

  Safety:
    - Motors are stopped on boot.
    - Motors stop if no V command is received within COMMAND_TIMEOUT_MS.

  Notes:
    - Encoders are used as single-channel (x1) tachometers only.
    - Encoders are counted on their configured S1 pins via pin-change
      interrupts (PCINT2 group). S2 pins are retained for raw diagnostics.
    - Direction is inferred from the commanded motor direction: the ISR counts
      every rising edge as +1, and the control loop negates the tick delta when
      the target velocity command is negative. The direction-corrected deltas are
      accumulated into signed left_position/right_position values, which are
      reported in the E line so the Pi receives correct direction information.
    - This means distance is accurate but the robot cannot detect slip or unexpected
      direction changes from the encoders alone.
    - PID gains are deliberately conservative placeholders.
*/

#include <Arduino.h>

// ---------------- Pin mapping ----------------

// MX1508 motor driver PWM outputs (from the Nano's perspective).
// All selected pins support PWM on classic Nano.
const uint8_t LEFT_PWM_A = 6;   // HW-354 INC
const uint8_t LEFT_PWM_B = 5;   // HW-354 IND
const uint8_t RIGHT_PWM_A = 9;  // HW-354 INA
const uint8_t RIGHT_PWM_B = 10; // HW-354 INB

// Encoder/hall inputs, matching the existing board pinout.
// The left encoder counts on S1 (D3 / PD3 / PCINT19).
// The right encoder counts on S1 (D2 / PD2 / PCINT18).
// Both D2 and D3 are on port D and share the PCINT2 pin-change interrupt group.
//
// Both encoders are used as single-channel (x1) tachometers: only distance
// (magnitude) comes from the encoder step count. Direction (forward/backward)
// is inferred from the commanded motor direction (target velocity sign) in the
// control loop, as the hardware cannot provide it.
const uint8_t LEFT_ENC_S1 = 3;    // Motor A S1 — LIVE channel, counted via PCINT2
const uint8_t LEFT_ENC_S2 = 7;    // Motor A S2 — DEAD channel, debug only
const uint8_t RIGHT_ENC_S1 = 2;   // Motor B S1 — LIVE channel, counted via PCINT2
const uint8_t RIGHT_ENC_S2 = 4;   // Motor B S2 — DEAD channel, debug only

// ---------------- Configuration ----------------

const unsigned long SERIAL_BAUD = 115200;
const unsigned long CONTROL_PERIOD_MS = 20;  // 50 Hz
const unsigned long REPORT_PERIOD_MS = 50;   // 20 Hz
const unsigned long COMMAND_TIMEOUT_MS = 400;

const int MAX_PWM = 200;        // keep conservative for first tests; max is 255
const int MIN_EFFECTIVE_PWM = 40; // raised to help overcome stiction
const float TARGET_RAMP_TPS_PER_S = 200.0f;
const int MAX_PWM_STEP = 8;

// Direction inversion flags for motor outputs. Change during calibration.
// Encoder direction is now inferred from commanded motor direction, so there are
// no separate encoder-sign flags.
const int LEFT_MOTOR_SIGN = 1;
const int RIGHT_MOTOR_SIGN = -1;

// Simple PI controller gains. These are placeholders.
float KP = 0.8f;
float KI = 0.05f;
float KD = 0.0f;

// ---------------- State ----------------

// Raw ISR tick accumulators (always positive — magnitude only).
volatile long left_count = 0;
volatile long right_count = 0;

// Signed positions maintained by the control loop. These accumulate the
// direction-corrected tick deltas and are reported in the E line so the ROS
// node receives correctly-signed positions for odometry.
volatile long left_position = 0;
volatile long right_position = 0;

long last_left_count = 0;
long last_right_count = 0;

float left_command_tps = 0.0f;
float right_command_tps = 0.0f;
float left_target_tps = 0.0f;
float right_target_tps = 0.0f;
float left_measured_tps = 0.0f;
float right_measured_tps = 0.0f;

float left_integral = 0.0f;
float right_integral = 0.0f;
float left_last_error = 0.0f;
float right_last_error = 0.0f;

int left_pwm = 0;
int right_pwm = 0;

unsigned long last_control_ms = 0;
unsigned long last_report_ms = 0;
unsigned long last_command_ms = 0;

uint8_t last_left_s1_level = 0;
uint8_t last_left_s2_level = 0;
uint8_t last_right_s1_level = 0;
uint8_t last_right_s2_level = 0;
volatile uint8_t last_encoder_portd = 0;
unsigned long left_s1_edges = 0;
unsigned long left_s2_edges = 0;
unsigned long right_s1_edges = 0;
unsigned long right_s2_edges = 0;

char input_line[64];
uint8_t input_len = 0;

// ---------------- Encoder interrupts ----------------

// Both encoders: the counted signal for each motor is on S1 (left = D3, right = D2).
// Both D2 and D3 are on port D, so they share the PCINT2 pin-change interrupt
// group. Pin-change interrupts fire on both edges, so compare the current port
// state with the previous one and count only low-to-high transitions.
ISR(PCINT2_vect) {
  uint8_t current_portd = PIND;
  uint8_t rising_edges = current_portd & ~last_encoder_portd;
  if (rising_edges & _BV(PD3)) {
    left_count++;
  }
  if (rising_edges & _BV(PD2)) {
    right_count++;
  }
  last_encoder_portd = current_portd;
}

// ---------------- Motor output ----------------

void setMx1508Motor(uint8_t in_a, uint8_t in_b, int pwm_command) {
  pwm_command = constrain(pwm_command, -MAX_PWM, MAX_PWM);

  if (pwm_command > 0) {
    analogWrite(in_a, pwm_command);
    analogWrite(in_b, 0);
  } else if (pwm_command < 0) {
    analogWrite(in_a, 0);
    analogWrite(in_b, -pwm_command);
  } else {
    // Coast/stop.
    analogWrite(in_a, 0);
    analogWrite(in_b, 0);
  }
}

void applyMotorOutputs() {
  setMx1508Motor(LEFT_PWM_A, LEFT_PWM_B, LEFT_MOTOR_SIGN * left_pwm);
  setMx1508Motor(RIGHT_PWM_A, RIGHT_PWM_B, RIGHT_MOTOR_SIGN * right_pwm);
}

void stopMotors() {
  left_command_tps = 0.0f;
  right_command_tps = 0.0f;
  left_target_tps = 0.0f;
  right_target_tps = 0.0f;
  left_integral = 0.0f;
  right_integral = 0.0f;
  left_last_error = 0.0f;
  right_last_error = 0.0f;
  left_pwm = 0;
  right_pwm = 0;
  applyMotorOutputs();
}

// ---------------- Serial protocol ----------------

void handleLine(char *line) {
  // Trim leading spaces.
  while (*line == ' ' || *line == '\t') {
    line++;
  }

  if (line[0] == 'V') {
    long l = 0;
    long r = 0;
    if (sscanf(line + 1, "%ld %ld", &l, &r) == 2) {
      left_command_tps = (float)l;
      right_command_tps = -(float)r;
      last_command_ms = millis();
      // Do not acknowledge every velocity command: the Pi sends these at
      // control-loop rate, and ACK spam can interleave with periodic status.
    } else {
      Serial.println(F("ERR bad V"));
    }
  } else if (line[0] == 'S') {
    stopMotors();
    last_command_ms = millis();
    Serial.println(F("OK stop"));
  } else if (line[0] == '?') {
    reportStatus();
  } else if (line[0] == 'Z') {
    zeroEncoders();
    Serial.println(F("OK zero"));
  } else if (line[0] == 'R') {
    reportRawEncoderPins();
  } else if (line[0] == 'P') {
    float kp = KP;
    float ki = KI;
    float kd = KD;
    if (sscanf(line + 1, "%f %f %f", &kp, &ki, &kd) == 3) {
      KP = kp;
      KI = ki;
      KD = kd;
      Serial.println(F("OK pid"));
    } else {
      Serial.println(F("ERR bad P"));
    }
  } else {
    Serial.println(F("ERR unknown"));
  }
}

void readSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      input_line[input_len] = '\0';
      if (input_len > 0) {
        handleLine(input_line);
      }
      input_len = 0;
    } else if (input_len < sizeof(input_line) - 1) {
      input_line[input_len++] = c;
    } else {
      // Overflow: reset line buffer.
      input_len = 0;
      Serial.println(F("ERR line too long"));
    }
  }
}

// ---------------- Control loop ----------------

int updateOneMotor(
  float target_tps,
  float measured_tps,
  float &integral,
  float &last_error,
  int current_pwm,
  float dt_s
) {
  if (target_tps == 0.0f) {
    integral = 0.0f;
    last_error = 0.0f;
    return 0;
  }

  float target_magnitude = abs(target_tps);
  float measured_magnitude = abs(measured_tps);
  float error = target_magnitude - measured_magnitude;
  float candidate_integral = constrain(
    integral + error * dt_s,
    -1000.0f,
    1000.0f
  );
  float derivative = (error - last_error) / dt_s;

  float output = KP * error + KI * candidate_integral + KD * derivative;

  // Feedback changes PWM magnitude only. Direction always follows the target,
  // so an overspeed correction cannot accidentally reverse the motor.
  int requested_pwm_magnitude = abs(current_pwm) + (int)output;
  bool saturated_high = requested_pwm_magnitude > MAX_PWM && output > 0.0f;
  bool saturated_low = requested_pwm_magnitude < 0 && output < 0.0f;
  if (!saturated_high && !saturated_low) {
    integral = candidate_integral;
  }
  last_error = error;

  int new_pwm_magnitude = constrain(requested_pwm_magnitude, 0, MAX_PWM);

  if (new_pwm_magnitude != 0 && new_pwm_magnitude < MIN_EFFECTIVE_PWM) {
    new_pwm_magnitude = MIN_EFFECTIVE_PWM;
  }

  int current_pwm_magnitude = abs(current_pwm);
  if (new_pwm_magnitude > current_pwm_magnitude + MAX_PWM_STEP) {
    new_pwm_magnitude = current_pwm_magnitude + MAX_PWM_STEP;
  } else if (new_pwm_magnitude + MAX_PWM_STEP < current_pwm_magnitude) {
    new_pwm_magnitude = current_pwm_magnitude - MAX_PWM_STEP;
  }

  return (target_tps > 0.0f) ? new_pwm_magnitude : -new_pwm_magnitude;
}

void controlLoop() {
  unsigned long now = millis();
  unsigned long elapsed_ms = now - last_control_ms;
  if (elapsed_ms < CONTROL_PERIOD_MS) {
    return;
  }
  last_control_ms = now;

  if (now - last_command_ms > COMMAND_TIMEOUT_MS) {
    stopMotors();
    return;
  }

  float max_target_step = TARGET_RAMP_TPS_PER_S * (elapsed_ms / 1000.0f);
  left_target_tps += constrain(
    left_command_tps - left_target_tps,
    -max_target_step,
    max_target_step
  );
  right_target_tps += constrain(
    right_command_tps - right_target_tps,
    -max_target_step,
    max_target_step
  );

  long left_now;
  long right_now;
  noInterrupts();
  left_now = left_count;
  right_now = right_count;
  interrupts();

  long left_delta = left_now - last_left_count;
  long right_delta = right_now - last_right_count;
  last_left_count = left_now;
  last_right_count = right_now;

  // Encoder is single-channel (counts only up, magnitude only). Direction is
  // inferred from the commanded motor direction: negate the delta when the target
  // velocity is negative so the PID and reported tps have the correct polarity.
  // Only accumulate position when actively driving to avoid counting passive motion.
  if (left_target_tps != 0.0f) {
    if (left_target_tps < 0.0f) left_delta = -left_delta;
    left_position += left_delta;
  } else {
    left_delta = 0;
  }
  if (right_target_tps != 0.0f) {
    if (right_target_tps < 0.0f) right_delta = -right_delta;
    // The right motor command is inverted so positive external commands drive
    // the robot forward. Report its position in the same forward-positive
    // convention as the left side.
    right_position -= right_delta;
  } else {
    right_delta = 0;
  }

  float dt_s = elapsed_ms / 1000.0f;
  if (dt_s <= 0.0f) {
    return;
  }

  left_measured_tps = left_delta / dt_s;
  right_measured_tps = right_delta / dt_s;

  left_pwm = updateOneMotor(left_target_tps, left_measured_tps, left_integral, left_last_error, left_pwm, dt_s);
  right_pwm = updateOneMotor(right_target_tps, right_measured_tps, right_integral, right_last_error, right_pwm, dt_s);

  applyMotorOutputs();
}

void zeroEncoders() {
  noInterrupts();
  left_count = 0;
  right_count = 0;
  left_position = 0;
  right_position = 0;
  interrupts();

  last_left_count = 0;
  last_right_count = 0;
  left_measured_tps = 0.0f;
  right_measured_tps = 0.0f;
}

void pollEncoderPinChanges() {
  uint8_t left_s1 = digitalRead(LEFT_ENC_S1);
  uint8_t left_s2 = digitalRead(LEFT_ENC_S2);
  uint8_t right_s1 = digitalRead(RIGHT_ENC_S1);
  uint8_t right_s2 = digitalRead(RIGHT_ENC_S2);

  if (left_s1 != last_left_s1_level) {
    left_s1_edges++;
    last_left_s1_level = left_s1;
  }
  if (left_s2 != last_left_s2_level) {
    left_s2_edges++;
    last_left_s2_level = left_s2;
  }
  if (right_s1 != last_right_s1_level) {
    right_s1_edges++;
    last_right_s1_level = right_s1;
  }
  if (right_s2 != last_right_s2_level) {
    right_s2_edges++;
    last_right_s2_level = right_s2;
  }
}

void reportRawEncoderPins() {
  Serial.print(F("R "));
  Serial.print(millis());
  Serial.print(' ');
  Serial.print(digitalRead(LEFT_ENC_S1));
  Serial.print(' ');
  Serial.print(digitalRead(LEFT_ENC_S2));
  Serial.print(' ');
  Serial.print(digitalRead(RIGHT_ENC_S1));
  Serial.print(' ');
  Serial.print(digitalRead(RIGHT_ENC_S2));
  Serial.print(' ');
  Serial.print(left_s1_edges);
  Serial.print(' ');
  Serial.print(left_s2_edges);
  Serial.print(' ');
  Serial.print(right_s1_edges);
  Serial.print(' ');
  Serial.println(right_s2_edges);
}

void reportStatus() {
  long left_now;
  long right_now;
  noInterrupts();
  left_now = left_position;
  right_now = right_position;
  interrupts();

  Serial.print(F("E "));
  Serial.print(millis());
  Serial.print(' ');
  Serial.print(left_now);
  Serial.print(' ');
  Serial.print(right_now);
  Serial.print(' ');
  Serial.print((long)left_measured_tps);
  Serial.print(' ');
  Serial.print((long)right_measured_tps);
  Serial.print(' ');
  Serial.print(left_pwm);
  Serial.print(' ');
  Serial.println(right_pwm);
}

void maybeReport() {
  unsigned long now = millis();
  if (now - last_report_ms >= REPORT_PERIOD_MS) {
    last_report_ms = now;
    reportStatus();
  }
}

// ---------------- Arduino entry points ----------------

void setup() {
  pinMode(LEFT_PWM_A, OUTPUT);
  pinMode(LEFT_PWM_B, OUTPUT);
  pinMode(RIGHT_PWM_A, OUTPUT);
  pinMode(RIGHT_PWM_B, OUTPUT);

  stopMotors();

  pinMode(LEFT_ENC_S1, INPUT_PULLUP);
  pinMode(LEFT_ENC_S2, INPUT_PULLUP);
  pinMode(RIGHT_ENC_S1, INPUT_PULLUP);
  pinMode(RIGHT_ENC_S2, INPUT_PULLUP);

  last_left_s1_level = digitalRead(LEFT_ENC_S1);
  last_left_s2_level = digitalRead(LEFT_ENC_S2);
  last_right_s1_level = digitalRead(RIGHT_ENC_S1);
  last_right_s2_level = digitalRead(RIGHT_ENC_S2);

  // Both encoders use pin-change interrupts on PCINT2 (PD0-PD7 group):
  //   Left encoder: D3 (PD3 / PCINT19, S1)
  //   Right encoder: D2 (PD2 / PCINT18, S1)
  // S2 channels (D7/D4) are retained for raw-pin debugging only.
  // NOTE: D0/D1 carry serial traffic, so PCINT2_vect also fires during UART RX,
  // but the ISR only checks PD2 and PD3, so it is harmless — minor ISR overhead
  // during serial bursts, negligible for a slow tracked robot.
  last_encoder_portd = PIND;
  PCICR |= _BV(PCIE2);
  PCMSK2 |= _BV(PCINT19); // D3 = PD3 = PCINT19 (left encoder S1)
  PCMSK2 |= _BV(PCINT18); // D2 = PD2 = PCINT18 (right encoder S1)
  PCIFR |= _BV(PCIF2);    // clear any pending flag

  Serial.begin(SERIAL_BAUD);
  last_control_ms = millis();
  last_report_ms = millis();
  last_command_ms = 0;

  Serial.println(F("BOOT arduino_nano_base_controller"));
}

void loop() {
  pollEncoderPinChanges();
  readSerial();
  controlLoop();
  maybeReport();
}
