"""Servo control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from websockets.asyncio.server import ServerConnection

try:
    from gpiozero import AngularServo
except ImportError:  # pragma: no cover - expected on non-hardware dev machines
    AngularServo = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from gpiozero import AngularServo as AngularServoType

HORIZONTAL_GPIO = 12
VERTICAL_GPIO = 13
SERVO_MIN_PULSE_S = 0.001
SERVO_MAX_PULSE_S = 0.002
SERVO_FRAME_WIDTH_S = 0.02


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
        self.servo_x_device: AngularServoType | None = None
        self.servo_y_device: AngularServoType | None = None

        if AngularServo is None:
            self.logger.warning("gpiozero is not installed; servo commands will be simulated.")
            return

        try:
            self.servo_x_device = AngularServo(
                pin=HORIZONTAL_GPIO,
                min_angle=float(self.servo_min_deg),
                max_angle=float(self.servo_max_deg),
                min_pulse_width=SERVO_MIN_PULSE_S,
                max_pulse_width=SERVO_MAX_PULSE_S,
                frame_width=SERVO_FRAME_WIDTH_S,
            )
            self.servo_y_device = AngularServo(
                pin=VERTICAL_GPIO,
                min_angle=float(self.servo_min_deg),
                max_angle=float(self.servo_max_deg),
                min_pulse_width=SERVO_MIN_PULSE_S,
                max_pulse_width=SERVO_MAX_PULSE_S,
                frame_width=SERVO_FRAME_WIDTH_S,
            )
        except Exception:
            self.servo_x_device = None
            self.servo_y_device = None
            self.logger.warning(
                "Could not initialize gpiozero servos; servo commands will be simulated.",
                exc_info=True,
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
        clamped = self._clamp_servo(logical_angle)
        if axis == "x":
            if self.servo_x_device is None:
                return
            self.servo_x_device.angle = clamped
            return

        if self.servo_y_device is None:
            return
        self.servo_y_device.angle = clamped
