"""Audio control module for PetCar3.3."""

from __future__ import annotations

import logging

from websockets.asyncio.server import ServerConnection

from tts_control import TtsController


class AudioController:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.tts_handler = TtsController(logger=logger)

    async def handle_command(self, websocket: ServerConnection, raw_message: str) -> None:
        message = raw_message.strip()
        parts = message.split(maxsplit=2)

        if len(parts) < 2:
            await websocket.send("error invalid-audio-command")
            return

        subcommand = parts[1].lower()
        if subcommand == "t":
            text = parts[2].strip() if len(parts) >= 3 else ""
            await self.tts_handler.handle_command(websocket, text)
            return

        await websocket.send("error invalid-audio-command")

