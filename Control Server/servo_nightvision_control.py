"""Servo and nightvision control module for PetCar3.3.

This module is intentionally logging-only for now.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection


@dataclass(slots=True)
class ServoNightvisionState:
    servo_x: float = 0.0
    servo_y: float = 0.0
    nightvision_on: bool = False


class ServoNightvisionController:
    def __init__(self, logger: logging.Logger, servo_min_deg: int, servo_max_deg: int) -> None:
        self.logger = logger
        self.servo_min_deg = servo_min_deg
        self.servo_max_deg = servo_max_deg
        self.state = ServoNightvisionState()

    async def handle_servo_command(self, websocket: ServerConnection, parts: list[str]) -> None:
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

    async def handle_nightvision_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2:
            await websocket.send("error invalid-nightvision-command")
            return

        action = parts[1].lower()
        if action == "query":
            await websocket.send(f"n {'on' if self.state.nightvision_on else 'off'}")
            return
        if action in {"on", "off"}:
            self.state.nightvision_on = action == "on"
            self.logger.info(
                "Nightvision would turn %s",
                "ON" if self.state.nightvision_on else "OFF",
            )
            return

        await websocket.send("error invalid-nightvision-command")

    def set_servo(self, axis: str, angle: float, source: str) -> None:
        if axis == "x":
            self.state.servo_x = angle
        elif axis == "y":
            self.state.servo_y = angle
        else:
            self.logger.warning("Ignoring invalid servo axis from %s: %s", source, axis)
            return

        self.logger.info(
            "Servo would move: axis=%s angle=%.1f deg source=%s",
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
