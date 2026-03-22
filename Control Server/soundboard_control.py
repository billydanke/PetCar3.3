"""Soundboard control module for PetCar3.3 audio."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from websockets.asyncio.server import ServerConnection

SUPPORTED_SOUND_EXTENSIONS = {".wav"}


@dataclass(slots=True)
class SoundboardState:
    last_sound_id: str = ""


class SoundboardController:
    def __init__(self, logger: logging.Logger, player_binary: str = "aplay") -> None:
        self.logger = logger
        self.state = SoundboardState()
        self.player_binary = shutil.which(player_binary)
        self.soundboard_dir = Path(__file__).resolve().parent / "soundboard"
        self._queue: asyncio.Queue[tuple[str, Path]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

        if self.player_binary is None:
            self.logger.warning("%s is not installed or not on PATH; soundboard commands will return an error.", player_binary)

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) < 3:
            await websocket.send("error invalid-soundboard-command")
            return

        action = parts[2].lower()
        if action == "query":
            if len(parts) != 3:
                await websocket.send("error invalid-soundboard-command")
                return

            sound_ids = self.list_sound_ids()
            if sound_ids is None:
                await websocket.send("error soundboard-unavailable")
                return

            items = " ".join(sound_ids)
            response = f"a s items {items}" if items else "a s items"
            await websocket.send(response)
            return

        if action != "play":
            await websocket.send("error invalid-soundboard-command")
            return

        if len(parts) != 4:
            await websocket.send("error invalid-soundboard-command")
            return

        sound_id = parts[3].strip().lower()
        sound_path = self.resolve_sound_path(sound_id)
        if sound_path is None:
            await websocket.send("error unknown-sound")
            return

        if self.player_binary is None:
            await websocket.send("error soundboard-unavailable")
            return

        self.state.last_sound_id = sound_id
        self._ensure_worker()
        await self._queue.put((sound_id, sound_path))
        self.logger.info("Soundboard queued: %s", sound_id)
        await websocket.send(f"a s ok {sound_id}")

    def list_sound_ids(self) -> list[str] | None:
        if not self.soundboard_dir.exists():
            return []
        if not self.soundboard_dir.is_dir():
            self.logger.warning("Soundboard path is not a directory: %s", self.soundboard_dir)
            return None

        sound_ids: list[str] = []
        for path in sorted(self.soundboard_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_SOUND_EXTENSIONS:
                continue
            if not self._is_valid_sound_id(path.stem):
                self.logger.warning("Ignoring soundboard file with invalid sound id: %s", path.name)
                continue
            sound_ids.append(path.stem.lower())
        return sound_ids

    def resolve_sound_path(self, sound_id: str) -> Path | None:
        if not self._is_valid_sound_id(sound_id):
            return None

        candidate = (self.soundboard_dir / f"{sound_id}.wav").resolve()
        try:
            candidate.relative_to(self.soundboard_dir.resolve())
        except ValueError:
            return None

        if not candidate.is_file():
            return None
        return candidate

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._run_worker(), name="soundboard-worker")

    async def _run_worker(self) -> None:
        while True:
            sound_id, sound_path = await self._queue.get()
            try:
                await self._play_sound(sound_path)
                self.logger.info("Soundboard played: %s", sound_id)
            except Exception:
                self.logger.exception("Soundboard playback failed for '%s'", sound_id)
            finally:
                self._queue.task_done()

    async def _play_sound(self, sound_path: Path) -> None:
        process = await asyncio.create_subprocess_exec(
            self.player_binary,
            str(sound_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(error_text or f"{self.player_binary} exited with {process.returncode}")

    @staticmethod
    def _is_valid_sound_id(sound_id: str) -> bool:
        if not sound_id:
            return False
        return all(char.islower() or char.isdigit() or char == "_" for char in sound_id)
