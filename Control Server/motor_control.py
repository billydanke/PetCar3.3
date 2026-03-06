"""Motor control module for PetCar3.3.

This module is intentionally logging-only for now.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection


@dataclass(slots=True)
class MotorState:
    drive_vx_percent: float = 0.0
    drive_vy_percent: float = 0.0
    drive_rotation_percent: float = 0.0


class MotorController:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.state = MotorState()

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) < 5:
            await websocket.send("error invalid-motor-command")
            return

        try:
            values = self._parse_keyed_values(parts[1:])
        except ValueError as exc:
            await websocket.send(f"error {exc}")
            return

        vx = self._clamp_percent(values.get("x", 0.0))
        vy = self._clamp_percent(values.get("y", 0.0))
        rotation = self._clamp_percent(values.get("r", values.get("rot", 0.0)))
        self.set_drive(vx, vy, rotation)

    def set_drive(self, vx: float, vy: float, rotation: float) -> None:
        self.state.drive_vx_percent = vx
        self.state.drive_vy_percent = vy
        self.state.drive_rotation_percent = rotation
        self.logger.info(
            "Drive would move: translate_x=%.1f%% translate_y=%.1f%% rotate=%.1f%%",
            vx,
            vy,
            rotation
        )

    def hard_stop(self, reason: str) -> None:
        if (
            self.state.drive_vx_percent == 0.0
            and self.state.drive_vy_percent == 0.0
            and self.state.drive_rotation_percent == 0.0
        ):
            self.logger.info("Motor hard-stop confirmed (%s)", reason)
            return

        self.state.drive_vx_percent = 0.0
        self.state.drive_vy_percent = 0.0
        self.state.drive_rotation_percent = 0.0
        self.logger.warning("Motor hard-stop: %s", reason)

    @staticmethod
    def _parse_keyed_values(parts: list[str]) -> dict[str, float]:
        if len(parts) % 2 != 0:
            raise ValueError("invalid-keyed-values")

        values: dict[str, float] = {}
        for index in range(0, len(parts), 2):
            key = parts[index].lower()
            try:
                value = float(parts[index + 1])
            except ValueError as exc:
                raise ValueError("invalid-number") from exc
            values[key] = value
        return values

    @staticmethod
    def _clamp_percent(value: float) -> float:
        return max(-100.0, min(100.0, value))
