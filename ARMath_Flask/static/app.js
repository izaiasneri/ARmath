"use strict";

const $ = (id) => document.getElementById(id);
const video = $("video");
const preview = $("preview");
const capture = document.createElement("canvas");
const transform = ["scale", "x", "y", "z"];
const markerNames = Array.from(document.querySelectorAll("[data-marker-name]"),
  (name) => name.dataset.markerName);
const state = {
  mode: "idle", source: 0, stream: null, raw: null, frozen: null,
  marker: null, lastSeen: 0, busy: false, dirty: false,
  expression: $("expression").defaultValue, device: "",
};
let formulaUrl = "";

function setControl(id, message, icon) {
  const control = $(id);
  const label = control.querySelector(".control-label");
  if (label.textContent !== message) label.textContent = message;
  if (icon) control.querySelector("use").setAttribute("href", "#icon-" + icon);
}

function status(message, type) {
  setControl("camera-status", message);
  $("camera-status").dataset.state = type;
}

function showMarker(marker) {
  state.marker = marker;
  $("marker-id").textContent = "ID do cartão · " + (marker ?? "—");
  $("surface-name").textContent = marker === null ? "Aponte a câmera para um marcador" : markerNames[marker];
  const formula = $("formula");
  formula.hidden = marker === null;
  if (marker === null) return;
  const query = new URLSearchParams({theme: document.documentElement.dataset.theme});
  if (marker === 9) query.set("expression", state.expression);
  const url = "/api/formula/" + marker + ".png?" + query;
  if (url !== formulaUrl) {
    formula.alt = marker === 9 ? "f(x,y) = " + state.expression : "Equação de " + markerNames[marker];
    formula.src = url;
    formulaUrl = url;
  }
}

function showPreview(visible) {
  preview.hidden = !visible;
  $("placeholder").hidden = visible;
  $("save").disabled = !visible;
  $("menu-save").disabled = !visible;
  $("freeze").disabled = !visible || state.mode === "demo";
  $("demo-camera").hidden = !visible || state.mode !== "demo";
  const frozen = state.mode === "frozen";
  setControl("freeze", frozen ? "Retomar vídeo" : "Congelar imagem", frozen ? "play" : "pause");
}

function resetSource() {
  state.source += 1;
  state.stream?.getTracks().forEach((track) => track.stop());
  video.srcObject = null;
  state.stream = state.raw = state.frozen = null;
  state.mode = "idle";
  state.dirty = false;
  state.lastSeen = 0;
  $("camera-error").hidden = true;
  setControl("start", "Ativar câmera", "camera");
  showPreview(false);
  showMarker(null);
  $("cut").textContent = $("plane-toggle").checked ? "Aponte para um marcador" : "Ative o plano";
}

function sourceError(message) {
  resetSource();
  setControl("start", "Reiniciar câmera", "reset");
  $("camera-error").textContent = message;
  $("camera-error").hidden = false;
  status("Indisponível", "error");
}

async function startCamera() {
  resetSource();
  const source = state.source;
  status("Conectando…", "idle");
  $("start").disabled = true;
  try {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Abra a página pelo localhost ou por HTTPS para usar a webcam.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        width: {ideal: 640}, height: {ideal: 480},
        ...(state.device ? {deviceId: {exact: state.device}} : {}),
      },
    });
    if (source !== state.source) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    state.stream = stream;
    const track = stream.getVideoTracks()[0];
    track.addEventListener("ended", () => {
      if (source === state.source) sourceError("A webcam foi desconectada. Tente reiniciar a câmera.");
    });
    video.srcObject = stream;
    await video.play();
    if (source !== state.source) return;
    state.mode = "live";
    status("Ao vivo · Aguardando marcador", "live");
    renderFrame();
  } catch (error) {
    if (source === state.source) {
      const messages = {
        NotAllowedError: "Permita o acesso à câmera no navegador e tente novamente.",
        NotFoundError: "Nenhuma câmera foi encontrada. Conecte ou selecione outro dispositivo.",
        NotReadableError: "A câmera está ocupada ou indisponível. Feche outros aplicativos que possam estar usando a webcam.",
        OverconstrainedError: "A câmera selecionada está indisponível. Escolha outro dispositivo.",
      };
      sourceError(messages[error.name] || error.message);
    }
  } finally {
    $("start").disabled = false;
  }
}

function jpegFromCapture() {
  return new Promise((resolve) => capture.toBlob(resolve, "image/jpeg", 0.9));
}

async function renderFrame() {
  if (state.busy || state.mode === "idle") return;
  if (state.mode !== "live" && !state.dirty) return;
  state.busy = true;
  state.dirty = false;
  const source = state.source;
  const mode = state.mode;
  try {
    let raw = state.frozen;
    if (mode === "live") {
      if (!video.videoWidth) return;
      const ratio = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
      capture.width = Math.round(video.videoWidth * ratio);
      capture.height = Math.round(video.videoHeight * ratio);
      capture.getContext("2d").drawImage(video, 0, 0, capture.width, capture.height);
      raw = await jpegFromCapture();
    }
    if (source !== state.source || mode !== state.mode || !raw) return;

    const data = new FormData();
    data.set("frame", raw, "frame.jpg");
    data.set("expression", state.expression);
    for (const key of [...transform, "offset"]) data.set(key, $(key).value);
    for (const key of ["axes", "box", "grid"]) data.set(key, $(key).checked);
    if ($("plane-toggle").checked) data.set("plane", document.querySelector("[name=plane]:checked").value);

    const response = await fetch("/api/frame", {method: "POST", body: data});
    if (!response.ok) throw new Error("Não foi possível processar o quadro.");
    const image = await createImageBitmap(await response.blob());
    try {
      if (source !== state.source || mode !== state.mode) return;
      preview.width = image.width;
      preview.height = image.height;
      preview.getContext("2d").drawImage(image, 0, 0);
    } finally {
      image.close();
    }
    state.raw = raw;
    showPreview(true);
    const id = response.headers.get("X-Marker-Id");
    if (id !== null) {
      state.lastSeen = performance.now();
      showMarker(Number(id));
    } else if (mode !== "live" || performance.now() - state.lastSeen > 350) {
      showMarker(null);
    }
    const liveText = state.marker === null ? "Ao vivo · Aguardando marcador" : "Ao vivo · Marcador reconhecido";
    const message = {live: liveText, frozen: "Imagem congelada", demo: "Demonstração"}[mode];
    status(message, mode === "live" ? "live" : "frozen");
    $("cut").textContent = !$("plane-toggle").checked ? "Ative o plano"
      : response.headers.get("X-Cut-Coordinate") || "Aponte para um marcador";
  } catch (error) {
    if (source === state.source && mode === state.mode) sourceError(error.message);
  } finally {
    state.busy = false;
    if (state.mode === "live") setTimeout(renderFrame, 65);
    else if (state.dirty) setTimeout(renderFrame, 0);
  }
}

function refresh() {
  state.dirty = true;
  renderFrame();
}

function toggleFreeze() {
  if (state.mode === "live" && state.raw) {
    state.mode = "frozen";
    state.frozen = state.raw;
    status("Imagem congelada", "frozen");
  } else if (state.mode === "frozen") {
    state.mode = "live";
    state.frozen = null;
  } else {
    return;
  }
  showPreview(true);
  refresh();
}

async function demonstrate(url) {
  resetSource();
  const source = state.source;
  const marker = new Image();
  marker.src = url;
  try {
    await marker.decode();
    if (source !== state.source) return;
    capture.width = 640;
    capture.height = 480;
    const ctx = capture.getContext("2d");
    ctx.fillStyle = "#d9dfe9";
    ctx.fillRect(0, 0, 640, 480);
    ctx.drawImage(marker, 180, 106, 280, 280);
    const raw = await jpegFromCapture();
    if (source !== state.source) return;
    state.frozen = raw;
    state.mode = "demo";
    refresh();
  } catch {
    if (source === state.source) sourceError("Não foi possível carregar o marcador.");
  }
}

function savePhoto() {
  if (preview.hidden) return;
  preview.toBlob((photo) => {
    if (!photo) return;
    const url = URL.createObjectURL(photo);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ARMath-" + new Date().toISOString().replace(/[:.]/g, "-") + ".png";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, "image/png");
}

async function selectCamera() {
  const dialog = $("devices");
  if (!dialog.open) dialog.showModal();
  const select = $("device");
  try {
    const devices = await navigator.mediaDevices?.enumerateDevices() || [];
    select.replaceChildren(new Option("Câmera padrão", ""));
    for (const [index, device] of devices.filter((item) => item.kind === "videoinput").entries()) {
      if (device.deviceId) select.add(new Option(device.label || "Câmera " + (index + 1), device.deviceId));
    }
    select.value = Array.from(select.options).some((option) => option.value === state.device) ? state.device : "";
  } catch {
    select.value = "";
  }
}

function endSession() {
  resetSource();
  status("Câmera desligada", "idle");
}

function toggleAxes() {
  $("axes").checked = !$("axes").checked;
  refresh();
}

function updateSlider(key) {
  const value = Number($(key).value);
  const number = value.toLocaleString("pt-BR", {maximumFractionDigits: 2});
  document.querySelector('output[for="' + key + '"]').textContent =
    key === "scale" ? number + "×" : key === "offset" ? Math.round(value * 100) + "%" : number + "°";
}

function resetSliders(keys) {
  for (const key of keys) {
    $(key).value = $(key).defaultValue;
    updateSlider(key);
  }
  refresh();
}

$("start").addEventListener("click", startCamera);
$("demo-camera").addEventListener("click", startCamera);
$("menu-restart").addEventListener("click", startCamera);
$("menu-camera").addEventListener("click", selectCamera);
$("camera-select").addEventListener("click", selectCamera);
$("use-device").addEventListener("click", () => {
  state.device = $("device").value;
  $("devices").close();
  startCamera();
});
$("freeze").addEventListener("click", toggleFreeze);
$("save").addEventListener("click", savePhoto);
$("menu-save").addEventListener("click", savePhoto);
$("menu-axes").addEventListener("click", toggleAxes);
$("menu-exit").addEventListener("click", endSession);
$("reset").addEventListener("click", () => resetSliders(transform));
$("plane-toggle").addEventListener("change", () => {
  $("plane-settings").disabled = !$("plane-toggle").checked;
  $("cut").textContent = $("plane-toggle").checked ? "Aponte para um marcador" : "Ative o plano";
  refresh();
});
for (const control of document.querySelectorAll("#axes, #box, #grid, [name=plane]")) {
  control.addEventListener("change", refresh);
}
for (const key of [...transform, "offset"]) {
  $(key).addEventListener("input", () => {
    updateSlider(key);
    refresh();
  });
}
for (const button of document.querySelectorAll("[data-reset]")) {
  button.addEventListener("click", () => resetSliders([button.dataset.reset]));
}
for (const button of document.querySelectorAll("[data-dialog]")) {
  button.addEventListener("click", () => $(button.dataset.dialog).showModal());
}
for (const button of document.querySelectorAll("[data-demo]")) {
  button.addEventListener("click", () => {
    $("markers").close();
    demonstrate(button.dataset.demo);
  });
}
for (const menu of document.querySelectorAll(".menu")) {
  menu.querySelector(".popover").addEventListener("click", (event) => {
    if (event.target.closest("button, a")) menu.open = false;
  });
  menu.addEventListener("toggle", () => {
    if (!menu.open) return;
    for (const other of document.querySelectorAll(".menu[open]")) {
      if (other !== menu) other.open = false;
    }
  });
}
$("theme").addEventListener("click", () => {
  const root = document.documentElement;
  const light = root.dataset.theme !== "light";
  root.dataset.theme = light ? "light" : "dark";
  setControl("theme", light ? "Modo escuro" : "Modo claro", light ? "moon" : "sun");
  showMarker(state.marker);
});
$("clear").addEventListener("click", () => {
  $("expression").value = "";
  $("expression").focus();
  $("function-status").textContent = "Domínio [−5, 5] × [−5, 5]";
});
$("function-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("[type=submit]");
  button.disabled = true;
  try {
    const response = await fetch("/api/function", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({expression: $("expression").value}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Não foi possível plotar a função.");
    state.expression = data.expression;
    $("function-status").textContent = "Função atualizada para o marcador 9.";
    refresh();
  } catch (error) {
    $("function-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
document.addEventListener("keydown", (event) => {
  if ((!event.ctrlKey && !event.metaKey) || event.altKey) return;
  const key = event.key.toLowerCase();
  if (key === "s" && !preview.hidden) savePhoto();
  else if (key === "e") toggleAxes();
  else if (key === "q") endSession();
  else return;
  event.preventDefault();
});
window.addEventListener("pagehide", endSession);
