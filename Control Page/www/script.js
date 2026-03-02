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

let ws = null;
let current = { vx: 0, vy: 0, omega: 0 };
let intent = { vx: 0, vy: 0, omega: 0 };
let speedScale = Number(speedRange.value) / 100;
let sendTimer = null;
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
}

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
    return;
  }

  const url = wsUrlInput.value.trim();
  ws = new WebSocket(url);
  ws.addEventListener("open", () => setConnected(true));
  ws.addEventListener("close", () => setConnected(false));
  ws.addEventListener("error", () => setConnected(false));
  ws.addEventListener("message", handleMessage);
}

function send(data) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify(data));
}

function updateCurrentFromIntent() {
  current.vx = intent.vx * speedScale;
  current.vy = intent.vy * speedScale;
  current.omega = intent.omega * speedScale;
  driveOut.textContent =
    `vx=${current.vx.toFixed(2)} vy=${current.vy.toFixed(2)} w=${current.omega.toFixed(2)}`;
}

function applyDrive(vx, vy, omega) {
  const [nx, ny] = normalize(vx, vy);
  intent.vx = clamp(nx, -1, 1);
  intent.vy = clamp(ny, -1, 1);
  intent.omega = clamp(omega, -1, 1);
  updateCurrentFromIntent();
}

function sendDrive() {
  send({
    type: "drive",
    vx: Number(current.vx.toFixed(3)),
    vy: Number(current.vy.toFixed(3)),
    omega: Number(current.omega.toFixed(3))
  });
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
  battPacket.textContent = evt.data;

  try {
    const msg = JSON.parse(evt.data);
    if (typeof msg.battery === "number") {
      handleBattery(msg.battery);
    } else if (msg.type === "battery" && typeof msg.percent === "number") {
      handleBattery(msg.percent);
    } else if (msg.type === "status" && typeof msg.batteryPercent === "number") {
      handleBattery(msg.batteryPercent);
    }
  } catch {
    const numeric = Number(evt.data);
    if (!Number.isNaN(numeric)) handleBattery(numeric);
  }
}

function sendPanTilt() {
  const pan = Number(panRange.value);
  const tilt = Number(tiltRange.value);
  panVal.textContent = `${pan} deg`;
  tiltVal.textContent = `${tilt} deg`;
  send({ type: "camera", pan, tilt });
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

  let x = 0;
  let y = 0;
  let omega = 0;
  if (keys.has("w") || keys.has("arrowup")) y += 1;
  if (keys.has("s") || keys.has("arrowdown")) y -= 1;
  if (keys.has("a") || keys.has("arrowleft")) x -= 1;
  if (keys.has("d") || keys.has("arrowright")) x += 1;
  if (keys.has("q")) omega -= 1;
  if (keys.has("e")) omega += 1;
  applyDrive(x, y, omega);
  sendDrive();
  if (x !== 0 || y !== 0 || omega !== 0) beginContinuousSend();
});

window.addEventListener("keyup", (e) => {
  keys.delete(e.key.toLowerCase());

  let x = 0;
  let y = 0;
  let omega = 0;
  if (keys.has("w") || keys.has("arrowup")) y += 1;
  if (keys.has("s") || keys.has("arrowdown")) y -= 1;
  if (keys.has("a") || keys.has("arrowleft")) x -= 1;
  if (keys.has("d") || keys.has("arrowright")) x += 1;
  if (keys.has("q")) omega -= 1;
  if (keys.has("e")) omega += 1;
  applyDrive(x, y, omega);
  sendDrive();
  if (x === 0 && y === 0 && omega === 0) endContinuousSend();
});
