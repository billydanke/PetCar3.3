"""Motor control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

from arduino_serial import ArduinoSerialTransport


@dataclass(slots=True)
class MotorState:
    drive_vx_percent: int = 0
    drive_vy_percent: int = 0
    drive_rotation_percent: int = 0


class MotorController:
    def __init__(self, logger: logging.Logger, transport: ArduinoSerialTransport) -> None:
        self.logger = logger
        self.transport = transport
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

        vx = self._clamp_percent(values.get("x", 0))
        vy = self._clamp_percent(values.get("y", 0))
        rotation = self._clamp_percent(values.get("r", values.get("rot", 0)))
        await self.set_drive(vx, vy, rotation)

    async def set_drive(self, vx: int, vy: int, rotation: int) -> None:
        self.state.drive_vx_percent = vx
        self.state.drive_vy_percent = vy
        self.state.drive_rotation_percent = rotation

        sent = await self.transport.send_motor_command(vx, vy, rotation)
        if sent:
            self.logger.info(
                "Drive command sent: translate_x=%d%% translate_y=%d%% rotate=%d%%",
                vx,
                vy,
                rotation,
            )

    async def hard_stop(self, reason: str) -> None:
        if (
            self.state.drive_vx_percent == 0
            and self.state.drive_vy_percent == 0
            and self.state.drive_rotation_percent == 0
        ):
            self.logger.info("Motor hard-stop confirmed (%s)", reason)
            return

        self.state.drive_vx_percent = 0
        self.state.drive_vy_percent = 0
        self.state.drive_rotation_percent = 0
        await self.transport.send_motor_command(0, 0, 0)
        self.logger.warning("Motor hard-stop: %s", reason)

    @staticmethod
    def _parse_keyed_values(parts: list[str]) -> dict[str, int]:
        if len(parts) % 2 != 0:
            raise ValueError("invalid-keyed-values")

        values: dict[str, int] = {}
        for index in range(0, len(parts), 2):
            key = parts[index].lower()
            try:
                value = int(round(float(parts[index + 1])))
            except ValueError as exc:
                raise ValueError("invalid-number") from exc
            values[key] = value
        return values

    @staticmethod
    def _clamp_percent(value: int) -> int:
        return max(-100, min(100, value))
