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
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection, serve

from battery_control import BatteryController
from motor_control import MotorController
from servo_nightvision_control import ServoNightvisionController


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8889
    servo_min_deg: int = -90
    servo_max_deg: int = 90
    battery_min_percent: int = 0
    battery_max_percent: int = 100


class ControlServer:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("petcar.control_server")

        self.motorHandler = MotorController(self.logger)
        self.cameraHandler = ServoNightvisionController(logger=self.logger, servo_min_deg=self.config.servo_min_deg, servo_max_deg=self.config.servo_max_deg)
        self.batteryHandler = BatteryController(logger=self.logger, min_percent=self.config.battery_min_percent, max_percent=self.config.battery_max_percent)

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
            self.motorHandler.hard_stop(f"websocket disconnected: {client}")
            self.logger.info("Client disconnected: %s", client)

    async def _handle_message(self, websocket: ServerConnection, raw_message: str) -> None:
        message = raw_message.strip()
        if not message:
            return

        self.logger.info("Received '%s'", message)
        parts = message.split()
        command = parts[0].lower()

        if command == "m":
            await self.motorHandler.handle_command(websocket, parts)
            return
        if command == "s":
            await self.cameraHandler.handle_servo_command(websocket, parts)
            return
        if command == "n":
            await self.cameraHandler.handle_nightvision_command(websocket, parts)
            return
        if command == "b":
            await self.batteryHandler.handle_command(websocket, parts)
            return

        await websocket.send(f"error unknown-command {command}")
        self.logger.warning("Unsupported command: %s", message)

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
