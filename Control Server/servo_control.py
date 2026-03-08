"""Servo control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

try:
    from rpi_hardware_pwm import HardwarePWM
except ImportError:  # pragma: no cover - expected on non-hardware dev machines
    HardwarePWM = None  # type: ignore[assignment]

HORIZONTAL_GPIO = 12
VERTICAL_GPIO = 13
HORIZONTAL_PWM_CHANNEL = 0
VERTICAL_PWM_CHANNEL = 1
PWM_CHIP = 0
SERVO_FREQUENCY_HZ = 50
SERVO_MIN_PULSE_S = 0.001
SERVO_MAX_PULSE_S = 0.002
SERVO_PERIOD_S = 1.0 / SERVO_FREQUENCY_HZ


@dataclass(slots=True)
class ServoState:
    servo_x: float = 0.0
    servo_y: float = 0.0


class ServoController:
    def __init__(self, logger: logging.Logger, servo_min_deg: int, servo_max_deg: int) -> None:
        self.logger = logger
        self.servo_min_deg = servo_min_deg
        self.servo_max_deg = servo_max_deg
        self.state = ServoState()
        self.servo_x_pwm: HardwarePWM | None = None
        self.servo_y_pwm: HardwarePWM | None = None

        if HardwarePWM is None:
            self.logger.warning("rpi_hardware_pwm is not installed; servo commands will be simulated.")
            return

        try:
            self.servo_x_pwm = HardwarePWM(
                pwm_channel=HORIZONTAL_PWM_CHANNEL,
                hz=SERVO_FREQUENCY_HZ,
                chip=PWM_CHIP,
            )
            self.servo_y_pwm = HardwarePWM(
                pwm_channel=VERTICAL_PWM_CHANNEL,
                hz=SERVO_FREQUENCY_HZ,
                chip=PWM_CHIP,
            )
        except Exception:
            self.servo_x_pwm = None
            self.servo_y_pwm = None
            self.logger.warning(
                "Could not initialize hardware PWM servos; servo commands will be simulated.",
                exc_info=True,
            )
            return

        x_duty = self._logical_to_duty_cycle(self.state.servo_x)
        y_duty = self._logical_to_duty_cycle(self.state.servo_y)
        self.servo_x_pwm.start(x_duty)
        self.servo_y_pwm.start(y_duty)
        self.logger.info(
            "Hardware PWM servo control initialized (x GPIO=%d/PWM%d, y GPIO=%d/PWM%d)",
            HORIZONTAL_GPIO,
            HORIZONTAL_PWM_CHANNEL,
            VERTICAL_GPIO,
            VERTICAL_PWM_CHANNEL,
        )

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) == 2 and parts[1].lower() == "query":
            await websocket.send(self.servo_query_response())
            return

        if len(parts) != 3:
            await websocket.send("error invalid-servo-command")
            return

        axis = parts[1].lower()
        if axis not in {"x", "y"}:
            await websocket.send("error invalid-servo-axis")
            return

        angle = self._clamp_servo(self._safe_float(parts[2], 0.0))
        self.set_servo(axis, angle, source="legacy")

    def set_servo(self, axis: str, angle: float, source: str) -> None:
        if axis == "x":
            self.state.servo_x = angle
        elif axis == "y":
            self.state.servo_y = angle
        else:
            self.logger.warning("Ignoring invalid servo axis from %s: %s", source, axis)
            return

        self._write_axis(axis, angle)
        self.logger.info(
            "Servo move: axis=%s angle=%.1f deg source=%s",
            axis,
            angle,
            source,
        )

    def servo_query_response(self) -> str:
        return f"s x {self.state.servo_x:.1f} y {self.state.servo_y:.1f}"

    @staticmethod
    def _safe_float(value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _clamp_servo(self, angle: float) -> float:
        return max(self.servo_min_deg, min(self.servo_max_deg, angle))

    def _write_axis(self, axis: str, logical_angle: float) -> None:
        duty_cycle = self._logical_to_duty_cycle(logical_angle)
        if axis == "x":
            if self.servo_x_pwm is None:
                return
            self.servo_x_pwm.change_duty_cycle(duty_cycle)
            return

        if self.servo_y_pwm is None:
            return
        self.servo_y_pwm.change_duty_cycle(duty_cycle)

    def _logical_to_duty_cycle(self, logical_angle: float) -> float:
        clamped = self._clamp_servo(logical_angle)
        input_span = self.servo_max_deg - self.servo_min_deg
        if input_span <= 0:
            pulse_s = (SERVO_MIN_PULSE_S + SERVO_MAX_PULSE_S) / 2.0
            return (pulse_s / SERVO_PERIOD_S) * 100.0

        normalized = (clamped - self.servo_min_deg) / input_span
        pulse_s = SERVO_MIN_PULSE_S + normalized * (SERVO_MAX_PULSE_S - SERVO_MIN_PULSE_S)
        return (pulse_s / SERVO_PERIOD_S) * 100.0
