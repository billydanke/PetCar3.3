"""Audio control module for PetCar3.3."""

from __future__ import annotations

import logging

from websockets.asyncio.server import ServerConnection

from soundboard_control import SoundboardController
from tts_control import TtsController
from volume_control import VolumeController


class AudioController:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.tts_handler = TtsController(logger=logger)
        self.volume_handler = VolumeController(logger=logger)
        self.soundboard_handler = SoundboardController(logger=logger)

    async def handle_command(self, websocket: ServerConnection, raw_message: str) -> None:
        message = raw_message.strip()
        parts = message.split()

        if len(parts) < 2:
            await websocket.send("error invalid-audio-command")
            return

        subcommand = parts[1].lower()
        if subcommand == "t":
            text = self._extract_tts_text(message)
            await self.tts_handler.handle_command(websocket, text)
            return
        if subcommand == "v":
            await self.volume_handler.handle_command(websocket, parts)
            return
        if subcommand == "s":
            await self.soundboard_handler.handle_command(websocket, parts)
            return

        await websocket.send("error invalid-audio-command")

    @staticmethod
    def _extract_tts_text(message: str) -> str:
        parts = message.split(maxsplit=2)
        if len(parts) < 3:
            return ""
        return parts[2].strip()
