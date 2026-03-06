"""Battery control module for PetCar3.3.

This module is intentionally logging-only for now.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection


@dataclass(slots=True)
class BatteryState:
    battery_percent: int = 100


class BatteryController:
    def __init__(self, logger: logging.Logger, min_percent: int, max_percent: int) -> None:
        self.logger = logger
        self.min_percent = min_percent
        self.max_percent = max_percent
        self.state = BatteryState()

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2 or parts[1].lower() != "query":
            await websocket.send("error invalid-battery-command")
            return

        percent = self.sample_battery_percent()
        await websocket.send(f"b {percent}")

    def sample_battery_percent(self) -> int:
        self.state.battery_percent = random.randint(self.min_percent, self.max_percent)
        return self.state.battery_percent
