#!/usr/bin/env python3
"""PetCar3.3 websocket control server.

This server is intentionally logging-only for now. It accepts the text
protocol used by the control page:
- servo: ``s x 40``, ``s y -20``, ``s query``
- motor: ``m x 50 y 0 r 25``
- nightvision: ``n on``, ``n off``, ``n query``
- battery: ``b query``

Queries return websocket responses. Non-query commands log what the robot
would do without touching hardware yet.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection, serve


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8889
    servo_min_deg: int = -90
    servo_max_deg: int = 90
    battery_min_percent: int = 0
    battery_max_percent: int = 100


@dataclass(slots=True)
class RobotState:
    servo_x: float = 0.0
    servo_y: float = 0.0
    nightvision_on: bool = False
    battery_percent: int = 100
    drive_vx_percent: float = 0.0
    drive_vy_percent: float = 0.0
    drive_rotation_percent: float = 0.0


class ControlServer:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.state = RobotState()
        self.logger = logging.getLogger("petcar.control_server")

    async def handler(self, websocket: ServerConnection) -> None:
        client = self._client_name(websocket)
        self.logger.info("Client connected: %s", client)

        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except Exception:
            self.logger.exception("Connection error from %s", client)
            raise
        finally:
            self._hard_stop_motors(f"websocket disconnected: {client}")
            self.logger.info("Client disconnected: %s", client)

    async def _handle_message(self, websocket: ServerConnection, raw_message: str) -> None:
        message = raw_message.strip()
        if not message:
            return

        self.logger.info("RX %s", message)
        await self._handle_legacy_message(websocket, message)

    async def _handle_legacy_message(self, websocket: ServerConnection, message: str) -> None:
        parts = message.split()
        command = parts[0].lower()

        if command == "s":
            await self._handle_legacy_servo(websocket, parts)
            return
        if command == "m":
            await self._handle_legacy_motor(websocket, parts)
            return
        if command == "n":
            await self._handle_legacy_nightvision(websocket, parts)
            return
        if command == "b":
            await self._handle_legacy_battery(websocket, parts)
            return

        await websocket.send(f"error unknown-command {command}")
        self.logger.warning("Unsupported command: %s", message)

    async def _handle_legacy_servo(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) == 2 and parts[1].lower() == "query":
            await websocket.send(self._legacy_servo_query_response())
            return

        if len(parts) != 3:
            await websocket.send("error invalid-servo-command")
            return

        axis = parts[1].lower()
        if axis not in {"x", "y"}:
            await websocket.send("error invalid-servo-axis")
            return

        angle = self._clamp_servo(self._safe_float(parts[2], 0.0))
        self._set_servo(axis, angle, source="legacy")

    async def _handle_legacy_motor(self, websocket: ServerConnection, parts: list[str]) -> None:
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
        self._set_drive(vx, vy, rotation, source="legacy")

    async def _handle_legacy_nightvision(self, websocket: ServerConnection, parts: list[str]) -> None:
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

    async def _handle_legacy_battery(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2 or parts[1].lower() != "query":
            await websocket.send("error invalid-battery-command")
            return

        percent = self._sample_battery_percent()
        await websocket.send(f"b {percent}")

    def _set_servo(self, axis: str, angle: float, source: str) -> None:
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

    def _set_drive(self, vx: float, vy: float, rotation: float, source: str) -> None:
        self.state.drive_vx_percent = vx
        self.state.drive_vy_percent = vy
        self.state.drive_rotation_percent = rotation
        self.logger.info(
            "Drive would move: translate_x=%.1f%% translate_y=%.1f%% rotate=%.1f%% source=%s",
            vx,
            vy,
            rotation,
            source,
        )

    def _hard_stop_motors(self, reason: str) -> None:
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

    def _sample_battery_percent(self) -> int:
        self.state.battery_percent = random.randint(
            self.config.battery_min_percent,
            self.config.battery_max_percent,
        )
        self.logger.info("Battery query would return %d%%", self.state.battery_percent)
        return self.state.battery_percent

    def _legacy_servo_query_response(self) -> str:
        return f"s x {self.state.servo_x:.1f} y {self.state.servo_y:.1f}"

    @staticmethod
    def _safe_float(value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

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

    def _clamp_servo(self, angle: float) -> float:
        return max(self.config.servo_min_deg, min(self.config.servo_max_deg, angle))

    @staticmethod
    def _clamp_percent(value: float) -> float:
        return max(-100.0, min(100.0, value))

    @staticmethod
    def _client_name(websocket: ServerConnection) -> str:
        remote = websocket.remote_address
        return str(remote) if remote is not None else "unknown-client"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PetCar3.3 websocket control server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8889, help="Bind port")
    parser.add_argument("--servo-min", type=int, default=-90, help="Servo minimum angle")
    parser.add_argument("--servo-max", type=int, default=90, help="Servo maximum angle")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser


async def run_server(config: ServerConfig) -> None:
    controller = ControlServer(config)
    async with serve(controller.handler, config.host, config.port):
        controller.logger.info(
            "Control server listening on ws://%s:%d",
            config.host,
            config.port,
        )
        await asyncio.Future()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = ServerConfig(
        host=args.host,
        port=args.port,
        servo_min_deg=args.servo_min,
        servo_max_deg=args.servo_max,
    )
    asyncio.run(run_server(config))


if __name__ == "__main__":
    main()
