"""Servo control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from websockets.asyncio.server import ServerConnection

try:
    from adafruit_servokit import ServoKit
except (ImportError, NotImplementedError):  # pragma: no cover - expected on non-hardware dev machines
    ServoKit = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from adafruit_servokit import ServoKit as ServoKitType


HORIZONTAL_CHANNEL = 0
VERTICAL_CHANNEL = 1
SERVO_KIT_CHANNELS = 16


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
        self.kit: ServoKitType | None = None

        if ServoKit is None:
            self.logger.warning(
                "adafruit_servokit is not installed; servo commands will be simulated."
            )
            return

        try:
            self.kit = ServoKit(channels=SERVO_KIT_CHANNELS)
        except NotImplementedError:
            self.kit = None
            self.logger.warning(
                "ServoKit platform unsupported on this machine; servo commands will be simulated."
            )
            return

        self._write_axis("x", self.state.servo_x)
        self._write_axis("y", self.state.servo_y)
        self.logger.info(
            "ServoKit initialized (x channel=%d, y channel=%d)",
            HORIZONTAL_CHANNEL,
            VERTICAL_CHANNEL,
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
        if self.kit is None:
            return

        physical_angle = self._logical_to_physical(logical_angle)
        channel = HORIZONTAL_CHANNEL if axis == "x" else VERTICAL_CHANNEL
        self.kit.servo[channel].angle = physical_angle

    def _logical_to_physical(self, logical_angle: float) -> float:
        clamped = self._clamp_servo(logical_angle)
        # Control protocol uses centered angles (e.g. -90..90). ServoKit expects 0..180.
        return max(0.0, min(180.0, 90.0 + clamped))
