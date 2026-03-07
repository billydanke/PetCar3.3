"""Servo control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

try:
    import pigpio
except ImportError:  # pragma: no cover - expected on non-hardware dev machines
    pigpio = None  # type: ignore[assignment]


HORIZONTAL_GPIO = 12
VERTICAL_GPIO = 13
SERVO_MIN_PULSE_US = 1000
SERVO_MAX_PULSE_US = 2000


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
        self.pi: pigpio.pi | None = None

        if pigpio is None:
            self.logger.warning("pigpio is not installed; servo commands will be simulated.")
            return

        self.pi = pigpio.pi()
        if not self.pi.connected:
            self.pi = None
            self.logger.warning(
                "Could not connect to pigpio daemon; servo commands will be simulated."
            )
            return

        self._write_axis("x", self.state.servo_x)
        self._write_axis("y", self.state.servo_y)
        self.logger.info(
            "Direct GPIO servo control initialized (x GPIO=%d, y GPIO=%d)",
            HORIZONTAL_GPIO,
            VERTICAL_GPIO,
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
        if self.pi is None:
            return

        gpio_pin = HORIZONTAL_GPIO if axis == "x" else VERTICAL_GPIO
        pulsewidth = self._logical_to_pulsewidth(logical_angle)
        self.pi.set_servo_pulsewidth(gpio_pin, pulsewidth)

    def _logical_to_pulsewidth(self, logical_angle: float) -> int:
        clamped = self._clamp_servo(logical_angle)
        input_span = self.servo_max_deg - self.servo_min_deg
        if input_span <= 0:
            return int((SERVO_MIN_PULSE_US + SERVO_MAX_PULSE_US) / 2)

        normalized = (clamped - self.servo_min_deg) / input_span
        pulse = SERVO_MIN_PULSE_US + normalized * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)
        return int(round(pulse))
