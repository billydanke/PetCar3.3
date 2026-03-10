#!/usr/bin/env python3
"""PetCar3.3 websocket control server.

This server accepts the text protocol used by the control page:
- servo: ``s x 40``, ``s y -20``, ``s query``
- motor: ``m x 50 y 0 r 25``
- nightvision: ``n on``, ``n off``, ``n query``
- battery: ``b query``

Queries return websocket responses. Motor and battery commands are forwarded
to the Arduino over serial.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection, serve

from arduino_serial import ArduinoSerialConfig, ArduinoSerialTransport
from battery_control import BatteryController
from motor_control import MotorController
from nightvision_control import NightvisionController
from servo_control import ServoController


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    servo_min_deg: int = -90
    servo_max_deg: int = 90
    arduino_port: str = "/dev/serial0"
    arduino_baud_rate: int = 9600
    arduino_timeout_s: float = 0.5
    heartbeat_interval_s: float = 1.0


class ControlServer:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("petcar.control_server")
        self.arduino = ArduinoSerialTransport(
            logger=self.logger,
            config=ArduinoSerialConfig(
                port=self.config.arduino_port,
                baud_rate=self.config.arduino_baud_rate,
                timeout_s=self.config.arduino_timeout_s,
            ),
        )

        self.motorHandler = MotorController(self.logger, self.arduino)
        self.servoHandler = ServoController(
            logger=self.logger,
            servo_min_deg=self.config.servo_min_deg,
            servo_max_deg=self.config.servo_max_deg,
        )
        self.nightvisionHandler = NightvisionController(logger=self.logger)
        self.batteryHandler = BatteryController(logger=self.logger, transport=self.arduino)

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
            await self.motorHandler.hard_stop(f"websocket disconnected: {client}")
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
            await self.servoHandler.handle_command(websocket, parts)
            return
        if command == "n":
            await self.nightvisionHandler.handle_command(websocket, parts)
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

    async def run_heartbeat_loop(self) -> None:
        interval_s = max(0.1, self.config.heartbeat_interval_s)
        self.logger.info("Arduino heartbeat loop started at %.2fs interval", interval_s)

        try:
            while True:
                sent = await self.arduino.send_heartbeat()
                if not sent:
                    self.logger.debug("Arduino heartbeat send failed")
                await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            self.logger.info("Arduino heartbeat loop stopped")
            raise


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PetCar3.3 websocket control server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--servo-min", type=int, default=-90, help="Servo minimum angle")
    parser.add_argument("--servo-max", type=int, default=90, help="Servo maximum angle")
    parser.add_argument("--arduino-port", default="/dev/serial0", help="Arduino serial port")
    parser.add_argument("--arduino-baud", type=int, default=9600, help="Arduino serial baud rate")
    parser.add_argument("--arduino-timeout", type=float, default=0.5, help="Arduino serial read/write timeout in seconds")
    parser.add_argument("--heartbeat-interval", type=float, default=1.0, help="Seconds between Arduino heartbeat messages")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity")
    return parser


async def run_server(config: ServerConfig) -> None:
    controller = ControlServer(config)
    async with serve(controller.handler, config.host, config.port):
        heartbeat_task = asyncio.create_task(controller.run_heartbeat_loop(), name="arduino-heartbeat")
        controller.logger.info(
            "Control server listening on ws://%s:%d",
            config.host,
            config.port,
        )
        try:
            await asyncio.Future()
        finally:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)


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
        arduino_port=args.arduino_port,
        arduino_baud_rate=args.arduino_baud,
        arduino_timeout_s=args.arduino_timeout,
        heartbeat_interval_s=args.heartbeat_interval,
    )
    asyncio.run(run_server(config))


if __name__ == "__main__":
    main()
