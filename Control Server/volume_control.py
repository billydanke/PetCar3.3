"""Volume control module for PetCar3.3 audio."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

VOLUME_PERCENT_PATTERN = re.compile(r"\[(\d{1,3})%\]")


@dataclass(slots=True)
class VolumeState:
    volume_percent: int | None = None


class VolumeController:
    def __init__(self, logger: logging.Logger, mixer_name: str = "SoftMaster", mixer_binary: str = "amixer") -> None:
        self.logger = logger
        self.state = VolumeState()
        self.mixer_name = mixer_name
        self.mixer_binary = shutil.which(mixer_binary)

        if self.mixer_binary is None:
            self.logger.warning("%s is not installed or not on PATH; volume commands will return an error.", mixer_binary)

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 3:
            await websocket.send("error invalid-volume-command")
            return

        action = parts[2].lower()
        if action == "query":
            volume = await self.query_volume_percent()
            if volume is None:
                await websocket.send("error volume-read-failed")
                return

            await websocket.send(f"a v {volume}")
            return

        try:
            requested_volume = int(round(float(parts[2])))
        except ValueError:
            await websocket.send("error invalid-volume-command")
            return

        volume = await self.set_volume_percent(requested_volume)
        if volume is None:
            await websocket.send("error volume-set-failed")
            return

        await websocket.send(f"a v {volume}")

    async def query_volume_percent(self) -> int | None:
        if self.mixer_binary is None:
            return None

        process = await asyncio.create_subprocess_exec(
            self.mixer_binary,
            "sget",
            self.mixer_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(
                "Volume query failed for mixer '%s': %s",
                self.mixer_name,
                stderr.decode("utf-8", errors="replace").strip(),
            )
            return None

        output = stdout.decode("utf-8", errors="replace")
        volume = self._parse_volume_percent(output)
        if volume is None:
            self.logger.warning("Could not parse volume percent from amixer output for mixer '%s'", self.mixer_name)
            return None

        self.state.volume_percent = volume
        self.logger.info("Volume query: %d%%", volume)
        return volume

    async def set_volume_percent(self, requested_volume: int) -> int | None:
        if self.mixer_binary is None:
            return None

        clamped_volume = max(0, min(100, requested_volume))
        process = await asyncio.create_subprocess_exec(
            self.mixer_binary,
            "sset",
            self.mixer_name,
            f"{clamped_volume}%",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(
                "Volume set failed for mixer '%s': %s",
                self.mixer_name,
                stderr.decode("utf-8", errors="replace").strip(),
            )
            return None

        output = stdout.decode("utf-8", errors="replace")
        volume = self._parse_volume_percent(output)
        if volume is None:
            volume = clamped_volume

        self.state.volume_percent = volume
        self.logger.info("Volume set: %d%%", volume)
        return volume

    @staticmethod
    def _parse_volume_percent(output: str) -> int | None:
        matches = VOLUME_PERCENT_PATTERN.findall(output)
        if not matches:
            return None

        try:
            return max(0, min(100, int(matches[-1])))
        except ValueError:
            return None
