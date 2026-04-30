"""Battery control module for PetCar3.3."""

from __future__ import annotations

import asyncio
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
        self._query_task: asyncio.Task[None] | None = None
        self._pending_websockets: set[ServerConnection] = set()

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2 or parts[1].lower() != "query":
            await websocket.send("error invalid-battery-command")
            return

        self._pending_websockets.add(websocket)
        if self._query_task is None or self._query_task.done():
            self._query_task = asyncio.create_task(self._query_and_send(), name="battery-query")

    async def _query_and_send(self) -> None:
        while self._pending_websockets:
            percent = await self.transport.query_battery_percent()
            websockets = tuple(self._pending_websockets)
            self._pending_websockets.clear()

            if percent is None:
                self.logger.warning("Battery query failed")
                await self._send_to_all(websockets, "error battery-read-failed")
                continue

            self.state.battery_percent = percent
            self.logger.info("Battery query: %d%%", percent)
            await self._send_to_all(websockets, f"b {percent}")

    async def _send_to_all(self, websockets: tuple[ServerConnection, ...], message: str) -> None:
        for websocket in websockets:
            try:
                await websocket.send(message)
            except Exception:
                self.logger.debug("Could not send battery response to websocket", exc_info=True)
