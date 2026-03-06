"""Nightvision control module for PetCar3.3.

This module is intentionally logging-only for now.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection


@dataclass(slots=True)
class NightvisionState:
    nightvision_on: bool = False


class NightvisionController:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.state = NightvisionState()

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
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
