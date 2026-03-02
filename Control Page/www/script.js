const wsDot = document.getElementById("wsDot");
const wsState = document.getElementById("wsState");
const wsUrlInput = document.getElementById("wsUrl");
const connectBtn = document.getElementById("connectBtn");
const speedRange = document.getElementById("speedRange");
const speedVal = document.getElementById("speedVal");
const driveOut = document.getElementById("driveOut");
const panRange = document.getElementById("panRange");
const tiltRange = document.getElementById("tiltRange");
const panVal = document.getElementById("panVal");
const tiltVal = document.getElementById("tiltVal");
const batteryBar = document.getElementById("batteryBar");
const batteryText = document.getElementById("batteryText");
const battPacket = document.getElementById("battPacket");
const servoPacket = document.getElementById("servoPacket");
const nightvisionState = document.getElementById("nightvisionState");
const nightvisionOn = document.getElementById("nightvisionOn");
const nightvisionOff = document.getElementById("nightvisionOff");
const nightvisionQuery = document.getElementById("nightvisionQuery");

let ws = null;
let current = { x: 0, y: 0, r: 0 };
let intent = { x: 0, y: 0, r: 0 };
let speedScale = Number(speedRange.value) / 100;
let sendTimer = null;
let batteryTimer = null;
let activeButton = null;
const keys = new Set();

const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
const normalize = (x, y) => {
  const mag = Math.hypot(x, y);
  if (mag <= 1) return [x, y];
  return [x / mag, y / mag];
};

function setConnected(connected) {
  wsDot.classList.toggle("connected", connected);
  wsState.textContent = connected ? "Connected" : "Disconnected";
  connectBtn.textContent = connected ? "Disconnect" : "Connect";

  if (!connected) {
    stopBatteryPolling();
  }
}

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
    return;
  }

  const url = wsUrlInput.value.trim();
  ws = new WebSocket(url);
  ws.addEventListener("open", handleOpen);
  ws.addEventListener("close", handleClose);
  ws.addEventListener("error", handleClose);
  ws.addEventListener("message", handleMessage);
}

function handleOpen() {
  setConnected(true);
  send("s query");
  send("n query");
  send("b query");
  startBatteryPolling();
}

function handleClose() {
  setConnected(false);
}

function send(command) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(command);
}

function updateCurrentFromIntent() {
  current.x = Math.round(intent.x * speedScale * 100);
  current.y = Math.round(intent.y * speedScale * 100);
  current.r = Math.round(intent.r * speedScale * 100);
  driveOut.textContent = formatDriveCommand();
}

function applyDrive(x, y, rotation) {
  const [nx, ny] = normalize(x, y);
  intent.x = clamp(nx, -1, 1);
  intent.y = clamp(ny, -1, 1);
  intent.r = clamp(rotation, -1, 1);
  updateCurrentFromIntent();
}

function formatDriveCommand() {
  return `m x ${current.x} y ${current.y} r ${current.r}`;
}

function sendDrive() {
  send(formatDriveCommand());
}

function stopDrive() {
  applyDrive(0, 0, 0);
  sendDrive();
}

function beginContinuousSend() {
  if (sendTimer) return;
  sendTimer = setInterval(sendDrive, 80);
}

function endContinuousSend() {
  if (!sendTimer) return;
  clearInterval(sendTimer);
  sendTimer = null;
}

function startBatteryPolling() {
  if (batteryTimer) return;
  batteryTimer = setInterval(() => send("b query"), 3000);
}

function stopBatteryPolling() {
  if (!batteryTimer) return;
  clearInterval(batteryTimer);
  batteryTimer = null;
}

function bindHold(button, onPress, onRelease) {
  const press = (e) => {
    e.preventDefault();
    button.classList.add("active");
    activeButton = button;
    onPress();
  };

  const release = () => {
    button.classList.remove("active");
    if (activeButton === button) activeButton = null;
    onRelease();
  };

  ["mousedown", "touchstart", "pointerdown"].forEach((evt) => button.addEventListener(evt, press));
  ["mouseup", "mouseleave", "touchend", "touchcancel", "pointerup", "pointercancel"].forEach((evt) =>
    button.addEventListener(evt, release)
  );
}

function handleBattery(percent) {
  const p = clamp(Number(percent) || 0, 0, 100);
  batteryBar.style.width = `${p}%`;
  batteryText.textContent = `Battery ${p.toFixed(0)}%`;

  if (p < 20) {
    batteryBar.style.background = "linear-gradient(90deg, #f97316, #ef4444)";
  } else if (p < 45) {
    batteryBar.style.background = "linear-gradient(90deg, #f59e0b, #eab308)";
  } else {
    batteryBar.style.background = "linear-gradient(90deg, #22c55e, #84cc16)";
  }
}

function handleMessage(evt) {
  const message = evt.data.trim();
  battPacket.textContent = message;

  if (message.startsWith("b ")) {
    const parts = message.split(/\s+/);
    if (parts.length >= 2) handleBattery(parts[1]);
    return;
  }

  if (message.startsWith("s ")) {
    servoPacket.textContent = message;
    const parts = message.split(/\s+/);
    for (let i = 1; i < parts.length - 1; i += 2) {
      const axis = parts[i];
      const value = Number(parts[i + 1]);
      if (axis === "x" && !Number.isNaN(value)) {
        panRange.value = String(value);
        panVal.textContent = `${value} deg`;
      }
      if (axis === "y" && !Number.isNaN(value)) {
        tiltRange.value = String(value);
        tiltVal.textContent = `${value} deg`;
      }
    }
    return;
  }

  if (message === "n on" || message === "n off") {
    nightvisionState.textContent = message === "n on" ? "on" : "off";
    return;
  }
}

function sendServo(axis, value) {
  send(`s ${axis} ${value}`);
}

function sendPanTilt() {
  const pan = Number(panRange.value);
  const tilt = Number(tiltRange.value);
  panVal.textContent = `${pan} deg`;
  tiltVal.textContent = `${tilt} deg`;
  sendServo("x", pan);
  sendServo("y", tilt);
}

function updateDriveFromKeys() {
  let x = 0;
  let y = 0;
  let rotation = 0;

  if (keys.has("w") || keys.has("arrowup")) y += 1;
  if (keys.has("s") || keys.has("arrowdown")) y -= 1;
  if (keys.has("a") || keys.has("arrowleft")) x -= 1;
  if (keys.has("d") || keys.has("arrowright")) x += 1;
  if (keys.has("q")) rotation -= 1;
  if (keys.has("e")) rotation += 1;

  applyDrive(x, y, rotation);
  sendDrive();

  if (x !== 0 || y !== 0 || rotation !== 0) {
    beginContinuousSend();
  } else {
    endContinuousSend();
  }
}

document.querySelectorAll("button.ctrl[data-vx]").forEach((btn) => {
  bindHold(
    btn,
    () => {
      applyDrive(Number(btn.dataset.vx), Number(btn.dataset.vy), 0);
      sendDrive();
      beginContinuousSend();
    },
    () => {
      endContinuousSend();
      stopDrive();
    }
  );
});

const rotLeft = document.getElementById("rotLeft");
const rotRight = document.getElementById("rotRight");
const rotStop = document.getElementById("rotStop");
const stopBtn = document.getElementById("stopBtn");

bindHold(
  rotLeft,
  () => {
    applyDrive(0, 0, -1);
    sendDrive();
    beginContinuousSend();
  },
  () => {
    endContinuousSend();
    stopDrive();
  }
);

bindHold(
  rotRight,
  () => {
    applyDrive(0, 0, 1);
    sendDrive();
    beginContinuousSend();
  },
  () => {
    endContinuousSend();
    stopDrive();
  }
);

rotStop.addEventListener("click", stopDrive);
stopBtn.addEventListener("click", stopDrive);
connectBtn.addEventListener("click", connectWebSocket);
nightvisionOn.addEventListener("click", () => {
  send("n on");
  nightvisionState.textContent = "on";
});
nightvisionOff.addEventListener("click", () => {
  send("n off");
  nightvisionState.textContent = "off";
});
nightvisionQuery.addEventListener("click", () => send("n query"));

speedRange.addEventListener("input", () => {
  speedScale = Number(speedRange.value) / 100;
  speedVal.textContent = `${Math.round(speedScale * 100)}%`;
  updateCurrentFromIntent();
  sendDrive();
});

[panRange, tiltRange].forEach((el) => {
  el.addEventListener("input", sendPanTilt);
  el.addEventListener("change", sendPanTilt);
});

window.addEventListener("keydown", (e) => {
  const key = e.key.toLowerCase();
  if (["w", "a", "s", "d", "q", "e", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) {
    e.preventDefault();
  }

  keys.add(key);
  if (key === " ") {
    stopDrive();
    return;
  }

  updateDriveFromKeys();
});

window.addEventListener("keyup", (e) => {
  keys.delete(e.key.toLowerCase());
  updateDriveFromKeys();
});

updateCurrentFromIntent();
sendPanTilt();
