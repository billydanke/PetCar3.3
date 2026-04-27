"""Nightvision control module for PetCar3.3."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from websockets.asyncio.server import ServerConnection

try:
    from gpiozero import DigitalOutputDevice
except ImportError:  # pragma: no cover - expected on non-hardware dev machines
    DigitalOutputDevice = None  # type: ignore[assignment]

NIGHTVISION_GPIO = 26
NIGHTVISION_ACTIVE_HIGH = False


@dataclass(slots=True)
class NightvisionState:
    nightvision_on: bool = False


class NightvisionController:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.state = NightvisionState()
        self.output: DigitalOutputDevice | None = None

        if DigitalOutputDevice is None:
            self.logger.warning("gpiozero is not installed; nightvision commands will be simulated.")
            return

        try:
            self.output = DigitalOutputDevice(
                NIGHTVISION_GPIO,
                active_high=NIGHTVISION_ACTIVE_HIGH,
                initial_value=False,
            )
        except Exception:
            self.output = None
            self.logger.warning(
                "Could not initialize nightvision GPIO%d; nightvision commands will be simulated.",
                NIGHTVISION_GPIO,
                exc_info=True,
            )
            return

        self.logger.info(
            "Nightvision GPIO control initialized (GPIO=%d, active_high=%s)",
            NIGHTVISION_GPIO,
            NIGHTVISION_ACTIVE_HIGH,
        )

    async def handle_command(self, websocket: ServerConnection, parts: list[str]) -> None:
        if len(parts) != 2:
            await websocket.send("error invalid-nightvision-command")
            return

        action = parts[1].lower()
        if action == "query":
            await websocket.send(f"n {'on' if self.state.nightvision_on else 'off'}")
            return

        if action in {"on", "off"}:
            self.set_nightvision(action == "on")
            self.logger.info(
                "Nightvision turned %s",
                "ON" if self.state.nightvision_on else "OFF",
            )
            await websocket.send(f"n {'on' if self.state.nightvision_on else 'off'}")
            return

        await websocket.send("error invalid-nightvision-command")

    def set_nightvision(self, enabled: bool) -> None:
        self.state.nightvision_on = enabled

        if self.output is None:
            return

        if enabled:
            self.output.on()
        else:
            self.output.off()
