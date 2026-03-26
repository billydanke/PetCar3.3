const STORAGE_KEY = "petcar.controlPage.settings";
const SERVO_MIN = -90;
const SERVO_MAX = 90;
const SERVO_STEP = 5;
const DRIVE_REPEAT_MS = 200;
const SERVO_REPEAT_MS = 50;

const baseIpInput = document.getElementById("baseIp");
const cameraPortInput = document.getElementById("cameraPort");
const cameraPathInput = document.getElementById("cameraPath");
const wsPortInput = document.getElementById("wsPort");
const cameraUrlPreview = document.getElementById("cameraUrlPreview");
const wsUrlPreview = document.getElementById("wsUrlPreview");
const cameraFrame = document.getElementById("cameraFrame");
const connectBtn = document.getElementById("connectBtn");

const wsDot = document.getElementById("wsDot");
const wsState = document.getElementById("wsState");
const signalState = document.getElementById("signalState");

const batteryBar = document.getElementById("batteryBar");
const batteryText = document.getElementById("batteryText");
const battPacket = document.getElementById("battPacket");
const audioCard = document.getElementById("audioCard");
const audioToggle = document.getElementById("audioToggle");
const audioDetails = document.getElementById("audioDetails");
const audioVolume = document.getElementById("audioVolume");
const audioVolumeValue = document.getElementById("audioVolumeValue");
const ttsInput = document.getElementById("ttsInput");
const ttsSendBtn = document.getElementById("ttsSendBtn");
const soundSelect = document.getElementById("soundSelect");
const soundPlayBtn = document.getElementById("soundPlayBtn");
const driveOut = document.getElementById("driveOut");
const servoPacket = document.getElementById("servoPacket");
const nightvisionState = document.getElementById("nightvisionState");
const lastSentPacket = document.getElementById("lastSentPacket");
const lastRecvPacket = document.getElementById("lastRecvPacket");
const packetLog = document.getElementById("packetLog");

const crawlToggle = document.getElementById("crawlToggle");
const driveStop = document.getElementById("driveStop");
const driveButtons = new Map(
  Array.from(document.querySelectorAll("[data-drive-action]")).map((button) => [button.dataset.driveAction, button])
);

const servoPad = document.getElementById("servoPad");
const servoDot = document.getElementById("servoDot");
const homeBtn = document.getElementById("homeBtn");
const nightvisionToggle = document.getElementById("nightvisionToggle");

let ws = null;
let sendTimer = null;
let batteryTimer = null;
let servoTimer = null;
let pointerDriveAction = null;
let activeDriveAction = "stop";
let crawlEnabled = false;
let nightvisionEnabled = false;
let audioExpanded = false;
let audioVolumePercent = 50;
let soundboardItems = [];
let current = { x: 0, y: 0, r: 0 };
let servoState = { x: 0, y: 0 };
let driveKeys = new Set();
let driveKeyOrder = [];
let servoKeys = new Set();

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function setText(element, value) {
  if (element) {
    element.textContent = value;
  }
}

function isTypingTarget(target) {
  return Boolean(
    target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable)
  );
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (typeof parsed.baseIp === "string") baseIpInput.value = parsed.baseIp;
    if (typeof parsed.cameraPort === "string") cameraPortInput.value = parsed.cameraPort;
    if (typeof parsed.cameraPath === "string") cameraPathInput.value = parsed.cameraPath;
    if (typeof parsed.wsPort === "string") wsPortInput.value = parsed.wsPort;
  } catch {
    // Ignore malformed storage and continue with defaults.
  }
}

function saveSettings() {
  const settings = {
    baseIp: sanitizeBaseIp(baseIpInput.value),
    cameraPort: cameraPortInput.value.trim(),
    cameraPath: normalizeCameraPath(cameraPathInput.value),
    wsPort: wsPortInput.value.trim(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function sanitizeBaseIp(value) {
  return value.trim().replace(/^https?:\/\//i, "").replace(/\/+$/, "");
}

function normalizeCameraPath(value) {
  const trimmed = value.trim();
  if (!trimmed) return "/cam_audio";
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

function buildCameraUrl() {
  const baseIp = sanitizeBaseIp(baseIpInput.value);
  const cameraPort = cameraPortInput.value.trim() || "8889";
  const cameraPath = normalizeCameraPath(cameraPathInput.value);
  return `http://${baseIp}:${cameraPort}${cameraPath}`;
}

function buildWsUrl() {
  const baseIp = sanitizeBaseIp(baseIpInput.value);
  const wsPort = wsPortInput.value.trim() || "8080";
  return `ws://${baseIp}:${wsPort}`;
}

function refreshConnectionPreview(updateFrame = false) {
  const cameraUrl = buildCameraUrl();
  const wsUrl = buildWsUrl();
  cameraUrlPreview.textContent = cameraUrl;
  wsUrlPreview.textContent = wsUrl;
  if (updateFrame) {
    cameraFrame.src = cameraUrl;
  }
}

function setConnected(connected) {
  wsDot.classList.toggle("connected", connected);
  setText(wsState, connected ? "Connected" : "Disconnected");
  setText(connectBtn, connected ? "Disconnect" : "Connect");
  setText(signalState, connected ? "Pending" : "Unavailable");
  setAudioControlsEnabled(connected);

  if (!connected) {
    stopBatteryPolling();
  }
}

function appendPacketLog(direction, message) {
  const row = document.createElement("div");
  row.className = `packet-row ${direction}`;
  row.textContent = `${new Date().toLocaleTimeString()} ${direction.toUpperCase()} ${message}`;
  packetLog.prepend(row);

  while (packetLog.children.length > 19) {
    packetLog.removeChild(packetLog.lastChild);
  }
}

function send(command) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  ws.send(command);
  setText(lastSentPacket, command);
  appendPacketLog("tx", command);
  return true;
}

function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    ws.close();
    return;
  }

  refreshConnectionPreview(true);
  saveSettings();

  const url = buildWsUrl();
  setText(wsState, "Connecting");
  setText(connectBtn, "Cancel");
  setText(signalState, "Pending");
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
  send("a v query");
  send("a s query");
  startBatteryPolling();
}

function handleClose() {
  ws = null;
  setConnected(false);
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

function handleBattery(percent) {
  const value = clamp(Number(percent) || 0, 0, 100);
  batteryBar.style.width = `${value}%`;
  setText(batteryText, `${value.toFixed(0)}%`);

  if (value < 20) {
    batteryBar.style.background = "linear-gradient(90deg, #f97316, #ef4444)";
  } else if (value < 45) {
    batteryBar.style.background = "linear-gradient(90deg, #f59e0b, #eab308)";
  } else {
    batteryBar.style.background = "linear-gradient(90deg, #22c55e, #84cc16)";
  }
}

function setAudioPanelExpanded(expanded) {
  audioExpanded = expanded;
  audioCard.classList.toggle("is-collapsed", !expanded);
  audioToggle.setAttribute("aria-expanded", String(expanded));
  audioDetails.hidden = !expanded;
}

function setAudioControlsEnabled(enabled) {
  audioToggle.disabled = !enabled;
  audioVolume.disabled = !enabled;
  ttsInput.disabled = !enabled;
  ttsSendBtn.disabled = !enabled;
  soundSelect.disabled = !enabled || soundboardItems.length === 0;
  soundPlayBtn.disabled = !enabled || !soundSelect.value;
}

function setAudioVolume(percent) {
  audioVolumePercent = clamp(Number(percent) || 0, 0, 100);
  audioVolume.value = String(audioVolumePercent);
  setText(audioVolumeValue, `${audioVolumePercent}%`);
}

function setSoundboardItems(items) {
  soundboardItems = items;
  soundSelect.innerHTML = "";

  if (soundboardItems.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No sounds loaded";
    soundSelect.append(option);
    soundSelect.value = "";
    setAudioControlsEnabled(Boolean(ws && ws.readyState === WebSocket.OPEN));
    return;
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a sound";
  soundSelect.append(placeholder);

  soundboardItems.forEach((soundId) => {
    const option = document.createElement("option");
    option.value = soundId;
    option.textContent = soundId;
    soundSelect.append(option);
  });

  soundSelect.value = "";
  setAudioControlsEnabled(Boolean(ws && ws.readyState === WebSocket.OPEN));
}

function sendAudioVolume() {
  send(`a v ${audioVolume.value}`);
}

function sendTtsMessage() {
  const text = ttsInput.value.trim();
  if (!text) return;
  if (!send(`a t ${text}`)) return;
  ttsInput.value = "";
}

function playSelectedSound() {
  const soundId = soundSelect.value;
  if (!soundId) return;
  send(`a s play ${soundId}`);
}

function handleMessage(event) {
  const message = event.data.trim();
  setText(lastRecvPacket, message);
  appendPacketLog("rx", message);

  if (message.startsWith("b ")) {
    setText(battPacket, message);
    const parts = message.split(/\s+/);
    if (parts.length >= 2) handleBattery(parts[1]);
    return;
  }

  if (message.startsWith("s ")) {
    updateServoStateFromMessage(message);
    return;
  }

  if (message.startsWith("a v ")) {
    const parts = message.split(/\s+/);
    if (parts.length >= 3) setAudioVolume(parts[2]);
    return;
  }

  if (message.startsWith("a s items")) {
    const parts = message.split(/\s+/).slice(3);
    setSoundboardItems(parts);
    return;
  }

  if (message === "n on" || message === "n off") {
    setNightvisionEnabled(message === "n on");
  }
}

function formatDriveCommand() {
  return `m x ${current.x} y ${current.y} r ${current.r}`;
}

function actionToVector(action) {
  if (action === "forward") return { x: 0, y: 1, r: 0 };
  if (action === "backward") return { x: 0, y: -1, r: 0 };
  if (action === "left") return { x: -1, y: 0, r: 0 };
  if (action === "right") return { x: 1, y: 0, r: 0 };
  if (action === "rotate-left") return { x: 0, y: 0, r: -1 };
  if (action === "rotate-right") return { x: 0, y: 0, r: 1 };
  return { x: 0, y: 0, r: 0 };
}

function updateDriveVisuals() {
  driveButtons.forEach((button, action) => {
    const isActive = action === activeDriveAction;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  crawlToggle.classList.toggle("is-active", crawlEnabled);
  crawlToggle.setAttribute("aria-pressed", String(crawlEnabled));
}

function applyDriveAction(action) {
  activeDriveAction = action;
  const scale = crawlEnabled ? 40 : 100;
  const vector = actionToVector(action);
  current.x = vector.x * scale;
  current.y = vector.y * scale;
  current.r = vector.r * scale;
  setText(driveOut, formatDriveCommand());
  updateDriveVisuals();
}

function sendDrive() {
  send(formatDriveCommand());
}

function beginContinuousDriveSend() {
  if (sendTimer) return;
  sendTimer = setInterval(sendDrive, DRIVE_REPEAT_MS);
}

function endContinuousDriveSend() {
  if (!sendTimer) return;
  clearInterval(sendTimer);
  sendTimer = null;
}

function resolveKeyboardDriveAction() {
  for (let i = driveKeyOrder.length - 1; i >= 0; i -= 1) {
    const key = driveKeyOrder[i];
    if (!driveKeys.has(key)) continue;
    if (key === "w") return "forward";
    if (key === "a") return "left";
    if (key === "s") return "backward";
    if (key === "d") return "right";
    if (key === "q") return "rotate-left";
    if (key === "e") return "rotate-right";
  }
  return "stop";
}

function refreshDriveFromInputs() {
  const nextAction = pointerDriveAction || resolveKeyboardDriveAction();
  applyDriveAction(nextAction);

  if (nextAction === "stop") {
    endContinuousDriveSend();
  } else {
    beginContinuousDriveSend();
  }

  sendDrive();
}

function clearDriveInputsAndStop() {
  pointerDriveAction = null;
  driveKeys.clear();
  driveKeyOrder = [];
  applyDriveAction("stop");
  endContinuousDriveSend();
  sendDrive();
}

function toggleCrawl() {
  crawlEnabled = !crawlEnabled;
  applyDriveAction(activeDriveAction);
  sendDrive();
}

function isServoHome() {
  return Math.abs(servoState.x) < 1 && Math.abs(servoState.y) < 1;
}

function updateServoUi() {
  const xPercent = ((servoState.x - SERVO_MIN) / (SERVO_MAX - SERVO_MIN)) * 100;
  const yPercent = ((SERVO_MAX - servoState.y) / (SERVO_MAX - SERVO_MIN)) * 100;

  servoDot.style.left = `${clamp(xPercent, 0, 100)}%`;
  servoDot.style.top = `${clamp(yPercent, 0, 100)}%`;
  setText(servoPacket, `s x ${servoState.x} y ${servoState.y}`);

  const homeActive = isServoHome();
  homeBtn.classList.toggle("is-active", homeActive);
  homeBtn.setAttribute("aria-pressed", String(homeActive));
}

function updateServoStateFromMessage(message) {
  const parts = message.split(/\s+/);
  for (let i = 1; i < parts.length - 1; i += 2) {
    const axis = parts[i];
    const value = Number(parts[i + 1]);
    if ((axis === "x" || axis === "y") && !Number.isNaN(value)) {
      servoState[axis] = clamp(Math.round(value), SERVO_MIN, SERVO_MAX);
    }
  }
  updateServoUi();
}

function sendServoPosition(x, y) {
  const nextX = clamp(Math.round(x), SERVO_MIN, SERVO_MAX);
  const nextY = clamp(Math.round(y), SERVO_MIN, SERVO_MAX);
  const changedX = nextX !== servoState.x;
  const changedY = nextY !== servoState.y;

  if (!changedX && !changedY) return;

  servoState.x = nextX;
  servoState.y = nextY;
  updateServoUi();

  if (changedX) send(`s x ${nextX}`);
  if (changedY) send(`s y ${nextY}`);
}

function moveServoBy(dx, dy) {
  sendServoPosition(servoState.x + dx, servoState.y + dy);
}

function setServoFromPointer(clientX, clientY) {
  const rect = servoPad.getBoundingClientRect();
  const xRatio = clamp((clientX - rect.left) / rect.width, 0, 1);
  const yRatio = clamp((clientY - rect.top) / rect.height, 0, 1);
  const nextX = SERVO_MIN + xRatio * (SERVO_MAX - SERVO_MIN);
  const nextY = SERVO_MAX - yRatio * (SERVO_MAX - SERVO_MIN);
  sendServoPosition(nextX, nextY);
}

function homeServos() {
  sendServoPosition(0, 0);
}

function setNightvisionEnabled(enabled) {
  nightvisionEnabled = enabled;
  setText(nightvisionState, enabled ? "on" : "off");
  nightvisionToggle.classList.toggle("is-active", enabled);
  nightvisionToggle.setAttribute("aria-pressed", String(enabled));
}

function toggleNightvision() {
  const next = !nightvisionEnabled;
  setNightvisionEnabled(next);
  send(`n ${next ? "on" : "off"}`);
}

function refreshServoFromKeys() {
  let dx = 0;
  let dy = 0;
  if (servoKeys.has("arrowleft")) dx -= SERVO_STEP;
  if (servoKeys.has("arrowright")) dx += SERVO_STEP;
  if (servoKeys.has("arrowup")) dy += SERVO_STEP;
  if (servoKeys.has("arrowdown")) dy -= SERVO_STEP;

  if (dx === 0 && dy === 0) return false;

  moveServoBy(dx, dy);
  return true;
}

function beginServoKeyMotion() {
  if (servoTimer) return;
  servoTimer = setInterval(() => {
    if (!refreshServoFromKeys()) {
      endServoKeyMotion();
    }
  }, SERVO_REPEAT_MS);
}

function endServoKeyMotion() {
  if (!servoTimer) return;
  clearInterval(servoTimer);
  servoTimer = null;
}

function registerDriveKey(key) {
  if (driveKeys.has(key)) return;
  driveKeys.add(key);
  driveKeyOrder = driveKeyOrder.filter((entry) => entry !== key);
  driveKeyOrder.push(key);
}

function unregisterDriveKey(key) {
  driveKeys.delete(key);
  driveKeyOrder = driveKeyOrder.filter((entry) => entry !== key);
}

function bindDriveButton(button, action) {
  const press = (event) => {
    event.preventDefault();
    if (typeof button.setPointerCapture === "function") {
      button.setPointerCapture(event.pointerId);
    }
    pointerDriveAction = action;
    refreshDriveFromInputs();
  };

  const release = (event) => {
    event.preventDefault();
    if (typeof button.releasePointerCapture === "function" && button.hasPointerCapture?.(event.pointerId)) {
      button.releasePointerCapture(event.pointerId);
    }
    if (pointerDriveAction === action) {
      pointerDriveAction = null;
      refreshDriveFromInputs();
    }
  };

  button.addEventListener("pointerdown", press);
  button.addEventListener("pointerup", release);
  button.addEventListener("pointercancel", release);
  button.addEventListener("pointerleave", (event) => {
    if (event.buttons !== 1) {
      release(event);
    }
  });
}

loadSettings();
refreshConnectionPreview(true);
applyDriveAction("stop");
updateServoUi();
setNightvisionEnabled(false);
setAudioPanelExpanded(false);
setAudioVolume(50);
setSoundboardItems([]);
setConnected(false);

[baseIpInput, cameraPortInput, cameraPathInput, wsPortInput].forEach((input) => {
  input.addEventListener("input", () => refreshConnectionPreview(false));
  input.addEventListener("change", () => {
    refreshConnectionPreview(true);
    saveSettings();
  });
});

connectBtn.addEventListener("click", connectWebSocket);
audioToggle.addEventListener("click", () => setAudioPanelExpanded(!audioExpanded));
audioVolume.addEventListener("input", () => setAudioVolume(audioVolume.value));
audioVolume.addEventListener("change", sendAudioVolume);
ttsSendBtn.addEventListener("click", sendTtsMessage);
ttsInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  sendTtsMessage();
});
soundSelect.addEventListener("change", () => setAudioControlsEnabled(Boolean(ws && ws.readyState === WebSocket.OPEN)));
soundPlayBtn.addEventListener("click", playSelectedSound);
crawlToggle.addEventListener("click", () => toggleCrawl());
driveStop.addEventListener("click", () => clearDriveInputsAndStop());
homeBtn.addEventListener("click", homeServos);
nightvisionToggle.addEventListener("click", toggleNightvision);

driveButtons.forEach((button, action) => {
  if (action === "stop") return;
  bindDriveButton(button, action);
});

servoPad.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  servoPad.focus({ preventScroll: true });
  setServoFromPointer(event.clientX, event.clientY);
});

servoPad.addEventListener("pointermove", (event) => {
  if ((event.buttons & 1) !== 1) return;
  setServoFromPointer(event.clientX, event.clientY);
});

window.addEventListener("keydown", (event) => {
  if (isTypingTarget(event.target)) return;

  const key = event.key.toLowerCase();
  const isDriveKey = ["w", "a", "s", "d", "q", "e"].includes(key);
  const isServoKey = ["arrowup", "arrowdown", "arrowleft", "arrowright"].includes(key);
  const isSpecialKey = key === " " || key === "control" || key === "shift" || key === "h";

  if (isDriveKey || isServoKey || isSpecialKey) {
    event.preventDefault();
  }

  if (key === "control") {
    if (!event.repeat) toggleCrawl();
    return;
  }

  if (key === "shift") {
    if (!event.repeat) toggleNightvision();
    return;
  }

  if (key === "h") {
    if (!event.repeat) homeServos();
    return;
  }

  if (key === " ") {
    clearDriveInputsAndStop();
    return;
  }

  if (isDriveKey) {
    registerDriveKey(key);
    refreshDriveFromInputs();
    return;
  }

  if (isServoKey) {
    if (!servoKeys.has(key)) {
      servoKeys.add(key);
      refreshServoFromKeys();
    }
    beginServoKeyMotion();
  }
});

window.addEventListener("keyup", (event) => {
  if (isTypingTarget(event.target)) return;

  const key = event.key.toLowerCase();

  if (driveKeys.has(key)) {
    unregisterDriveKey(key);
    refreshDriveFromInputs();
  }

  if (servoKeys.has(key)) {
    servoKeys.delete(key);
    if (servoKeys.size === 0) {
      endServoKeyMotion();
    }
  }
});
