"""Battery control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

from arduino_serial import ArduinoSerialTransport


@dataclass(slots=True)
class BatteryState:
    battery_percent: int = 100


class BatteryController:
    def __init__(self, logger: logging.Logger, transport: ArduinoSerialTransport) -> None:
        self.logger = logger
        self.transport = transport
        self.state = BatteryState()

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2 or parts[1].lower() != "query":
            await websocket.send("error invalid-battery-command")
            return

        percent = await self.transport.query_battery_percent()
        if percent is None:
            await websocket.send("error battery-read-failed")
            return

        self.state.battery_percent = percent
        self.logger.info("Battery query: %d%%", percent)
        await websocket.send(f"b {percent}")
