"""Serial transport for the PetCar3.3 Arduino controller."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

try:
    import serial
except ImportError:  # pragma: no cover - expected on non-hardware dev machines
    serial = None  # type: ignore[assignment]


@dataclass(slots=True)
class ArduinoSerialConfig:
    port: str = "/dev/serial0"
    baud_rate: int = 19200
    timeout_s: float = 0.5


class ArduinoSerialTransport:
    def __init__(self, logger: logging.Logger, config: ArduinoSerialConfig) -> None:
        self.logger = logger
        self.config = config
        self._lock = asyncio.Lock()
        self._serial: serial.Serial | None = None
        self._warned_unavailable = False

        if serial is None:
            self.logger.warning("pyserial is not installed; Arduino serial commands will be unavailable.")
            return

        self._open_serial(initial=True)

    @property
    def is_available(self) -> bool:
        return self._serial is not None

    async def send_motor_command(self, x: int, y: int, rotation: int) -> bool:
        command = f"m x {x} y {y} r {rotation}"
        return await self.send_line(command)

    async def send_heartbeat(self) -> bool:
        return await self.send_line("h")

    async def query_battery_percent(self) -> int | None:
        response = await self.request_line("b query")
        if response is None:
            return None

        if response.lower().startswith("dbg "):
            self.logger.warning("Arduino debug response to battery query: %r", response)
            return None

        parts = response.split()
        if len(parts) != 2 or parts[0].lower() != "b":
            self.logger.warning("Unexpected battery response from Arduino: %r", response)
            return None

        try:
            percent = int(parts[1])
        except ValueError:
            self.logger.warning("Invalid battery percent from Arduino: %r", response)
            return None

        return percent #max(0, min(100, percent))

    async def send_line(self, command: str) -> bool:
        async with self._lock:
            return await asyncio.to_thread(self._send_line_blocking, command)

    async def request_line(self, command: str) -> str | None:
        async with self._lock:
            return await asyncio.to_thread(self._request_line_blocking, command)

    def _send_line_blocking(self, command: str) -> bool:
        if not self._ensure_serial():
            self._warn_unavailable(command)
            return False

        try:
            self._serial.write(f"{command}\n".encode("ascii"))
            self._serial.flush()
            return True
        except Exception:
            self.logger.warning("Failed to write Arduino serial command: %s", command, exc_info=True)
            self._handle_serial_failure()
            return False

    def _request_line_blocking(self, command: str) -> str | None:
        if not self._ensure_serial():
            self._warn_unavailable(command)
            return None

        try:
            self._serial.write(f"{command}\n".encode("ascii"))
            self._serial.flush()
            response_bytes = self._serial.readline()
        except Exception:
            self.logger.warning("Failed to query Arduino over serial: %s", command, exc_info=True)
            self._handle_serial_failure()
            return None

        if not response_bytes:
            self.logger.warning("Timed out waiting for Arduino response to '%s'", command)
            return None

        response = response_bytes.decode("ascii", errors="ignore").strip()
        if not response:
            self.logger.warning(
                "Arduino returned non-text or whitespace-only response to '%s': %s",
                command,
                response_bytes.hex(" "),
            )
            return None

        self.logger.debug("Arduino raw response to '%s': %r [%s]", command, response, response_bytes.hex(" "))
        return response

    def _warn_unavailable(self, command: str) -> None:
        if self._warned_unavailable:
            return

        self._warned_unavailable = True
        self.logger.warning("Arduino serial unavailable; dropping command: %s", command)

    def _ensure_serial(self) -> bool:
        if self._serial is not None:
            return True

        if serial is None:
            return False

        self._open_serial(initial=False)
        return self._serial is not None

    def _open_serial(self, initial: bool) -> None:
        if serial is None:
            self._serial = None
            return

        try:
            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baud_rate,
                timeout=self.config.timeout_s,
                write_timeout=self.config.timeout_s,
            )
        except Exception:
            self._serial = None
            message = (
                "Could not open Arduino serial port %s at %d baud; serial commands will be unavailable."
                if initial
                else "Could not reopen Arduino serial port %s at %d baud; serial commands remain unavailable."
            )
            self.logger.warning(message, self.config.port, self.config.baud_rate, exc_info=True)
            return

        self._warned_unavailable = False
        message = (
            "Arduino serial connected on %s at %d baud"
            if initial
            else "Arduino serial reconnected on %s at %d baud"
        )
        self.logger.info(message, self.config.port, self.config.baud_rate)

    def _handle_serial_failure(self) -> None:
        if self._serial is None:
            return

        try:
            self._serial.close()
        except Exception:
            self.logger.debug("Ignoring error while closing failed Arduino serial handle", exc_info=True)
        finally:
            self._serial = None
