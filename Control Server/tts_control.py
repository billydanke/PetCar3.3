"""Text-to-speech control module for PetCar3.3."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection


@dataclass(slots=True)
class TtsState:
    last_text: str = ""


class TtsController:
    def __init__(self, logger: logging.Logger, voice_binary: str = "espeak-ng") -> None:
        self.logger = logger
        self.state = TtsState()
        self.voice_binary = shutil.which(voice_binary)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

        if self.voice_binary is None:
            self.logger.warning("espeak-ng is not installed or not on PATH; TTS commands will return an error.")

    async def handle_command(self, websocket: ServerConnection, raw_message: str) -> None:
        message = raw_message.strip()
        text = message[1:].strip() if len(message) > 1 else ""
        if not text:
            await websocket.send("error invalid-tts-command")
            return

        if self.voice_binary is None:
            await websocket.send("error tts-unavailable")
            return

        self.state.last_text = text
        self._ensure_worker()
        await self._queue.put(text)
        self.logger.info("TTS queued: %s", text)
        await websocket.send("t ok")

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._run_worker(), name="tts-worker")

    async def _run_worker(self) -> None:
        while True:
            text = await self._queue.get()
            try:
                await self._speak_text(text)
                self.logger.info("TTS spoke: %s", text)
            except Exception:
                self.logger.exception("TTS playback failed for queued text: %s", text)
            finally:
                self._queue.task_done()

    async def _speak_text(self, text: str) -> None:
        process = await asyncio.create_subprocess_exec(
            self.voice_binary,
            "-ven-us",
            "-s100",
            text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(error_text or f"{self.voice_binary} exited with {process.returncode}")
