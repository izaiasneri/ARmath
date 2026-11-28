"use strict";

const $ = (id) => document.getElementById(id);
const video = $("video");
const preview = $("preview");
const capture = document.createElement("canvas");
const transform = ["scale", "x", "y", "z"];
const captureContext = capture.getContext("2d", {willReadFrequently: true});
const previewContext = preview.getContext("2d");
const markerTracker = vision.createTracker();
const state = {
  mode: "idle", source: 0, stream: null, markers: [], marker: null, timer: 0,
  geometry: surfaces.custom($("expression").defaultValue), device: "",
};

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
  const contourButton = $("contour-open");
  if (contourButton) contourButton.disabled = marker === null;
  const surface = marker === null ? null : surfaces.catalog[marker];
  $("marker-id").textContent = "ID do cartão · " + (marker ?? "—");
  $("surface-name").textContent = surface?.[0] ?? "Aponte a câmera para um marcador";
  const formula = $("formula");
  formula.hidden = !surface;
  const equation = marker === 9 ? state.geometry.latex : surface?.[1] ?? "";
  if (formula.dataset.equation !== equation) {
    formula.dataset.equation = equation;
    if (!equation) formula.replaceChildren();
    else if (window.katex) {
      window.katex.render(equation, formula, {
        displayMode: true,
        output: "htmlAndMathml",
        throwOnError: false,
      });
    } else {
      formula.replaceChildren(renderFormula(equation));
    }
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
  $("freeze").dataset.active = String(frozen);
  setControl("freeze", frozen ? "Retomar vídeo" : "Congelar imagem", frozen ? "play" : "pause");
}

function resetSource() {
  state.source += 1;
  state.stream?.getTracks().forEach((track) => track.stop());
  video.srcObject = null;
  state.stream = null;
  state.mode = "idle";
  state.markers = [];
  markerTracker.reset();
  clearTimeout(state.timer);
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

function renderFrame() {
  clearTimeout(state.timer);
  if (state.mode === "idle") return;
  try {
    if (state.mode === "live" && video.videoWidth) {
      const ratio = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
      const width = Math.round(video.videoWidth * ratio), height = Math.round(video.videoHeight * ratio);
      if (capture.width !== width || capture.height !== height) {
        capture.width = width;
        capture.height = height;
        markerTracker.reset();
      }
      captureContext.drawImage(video, 0, 0, width, height);
      const detections = vision.detect(captureContext.getImageData(0, 0, width, height));
      state.markers = markerTracker.update(detections, performance.now());
    }
    if (state.mode === "live" && !video.videoWidth) return;
    if (preview.width !== capture.width || preview.height !== capture.height) {
      preview.width = capture.width;
      preview.height = capture.height;
      $("placeholder").style.setProperty("--camera-aspect", preview.width + " / " + preview.height);
      preview.closest(".camera-stage")?.style.setProperty("--camera-ratio", preview.width / preview.height);
    }
    previewContext.drawImage(capture, 0, 0);
    const plane = $("plane-toggle").checked && document.querySelector("[name=plane]:checked").value;
    const cut = surfaces.draw(previewContext, state.markers, {
      scale: Number($("scale").value),
      angles: ["x", "y", "z"].map((key) => Number($(key).value)),
      plane, offset: Number($("offset").value),
      axes: $("axes").checked, box: $("box").checked, grid: $("grid").checked,
      planes: $("planes")?.checked,
    }, state.geometry);
    showPreview(true);
    showMarker(state.markers[0]?.id ?? null);
    const live = state.marker === null ? "Ao vivo · Aguardando marcador" : "Ao vivo · Marcador reconhecido";
    status({live, frozen: "Imagem congelada", demo: "Demonstração"}[state.mode],
      state.mode === "live" ? "live" : "frozen");
    $("cut").textContent = plane ? cut || "Aponte para um marcador" : "Ative o plano";
  } catch (error) {
    sourceError(error.message);
  } finally {
    if (state.mode === "live") state.timer = setTimeout(renderFrame, 65);
  }
}

function refresh() {
  renderFrame();
}

function toggleFreeze() {
  if (state.mode === "live" && !preview.hidden) state.mode = "frozen";
  else if (state.mode === "frozen") {
    markerTracker.reset();
    state.mode = "live";
  }
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
    captureContext.fillStyle = "#d9dfe9";
    captureContext.fillRect(0, 0, 640, 480);
    captureContext.drawImage(marker, 180, 106, 280, 280);
    state.markers = vision.detect(captureContext.getImageData(0, 0, 640, 480));
    state.mode = "demo";
    refresh();
  } catch {
    if (source === state.source) sourceError("Não foi possível carregar o marcador.");
  }
}
function savePhoto() {
  if (!preview.hidden) saveCanvas(preview,"ARMath");
}

function saveCanvas(canvas, name) {
  canvas.toBlob((photo) => {
    if (!photo) return;
    const url = URL.createObjectURL(photo);
    const link = document.createElement("a");
    link.href = url;
    link.download = name + "-" + new Date().toISOString().replace(/[:.]/g, "-") + ".png";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, "image/png");
}

function showContours() {
  if (state.marker === null) return;
  const marker = state.marker;
  const name = surfaces.catalog[marker][0];
  const canvas = $("contour-plot");
  const data = surfaces.contours(marker,state.geometry);
  canvas.setAttribute("aria-label","Curvas de nível de " + name + " no plano XY");
  $("contour-description").textContent = data.levels.length
    ? "Vista XY da superfície. Cada curva indica uma altura z constante."
    : "A superfície tem altura constante em toda a malha, sem curvas de nível isoladas.";
  drawContours(canvas,data,marker,name);
  $("contour-dialog").showModal();
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
$("camera-select")?.addEventListener("click", selectCamera);
$("use-device").addEventListener("click", () => {
  state.device = $("device").value;
  $("devices").close();
  startCamera();
});
$("freeze").addEventListener("click", toggleFreeze);
$("save").addEventListener("click", savePhoto);
$("contour-open")?.addEventListener("click", showContours);
$("contour-save")?.addEventListener("click", () => saveCanvas($("contour-plot"),"ARMath-curvas-de-nivel"));
$("menu-save").addEventListener("click", savePhoto);
$("menu-axes").addEventListener("click", toggleAxes);
$("menu-exit").addEventListener("click", endSession);
$("reset").addEventListener("click", () => resetSliders(transform));
$("plane-toggle").addEventListener("change", () => {
  $("plane-settings").disabled = !$("plane-toggle").checked;
  $("cut").textContent = $("plane-toggle").checked ? "Aponte para um marcador" : "Ative o plano";
  refresh();
});
for (const control of document.querySelectorAll("#axes, #box, [name=plane]")) {
  control.addEventListener("change", refresh);
}
for (const control of document.querySelectorAll("#grid, #planes")) {
  control.addEventListener("change", () => {
    const other = $(control.id === "grid" ? "planes" : "grid");
    if (control.checked && other) other.checked = false;
    refresh();
  });
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
const functionError = $("function-error");
functionError?.addEventListener("close", () => {
  const input = $("expression");
  input.value = "";
  input.focus();
});

$("function-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.markers.some(({id}) => id === 9)) {
    const markerRequired = $("marker-required");
    if (markerRequired && !markerRequired.open) markerRequired.showModal();
    else if (!markerRequired) $("function-status").textContent = "Mostre o cartão 9 em frente à câmera.";
    return;
  }
  const entered = $("expression").value;
  try {
    state.geometry = surfaces.custom(entered.trim());
  } catch (error) {
    $("function-status").textContent = error.message;
    if (functionError) {
      $("invalid-expression").textContent = entered || "(campo vazio)";
      $("function-error-reason").textContent = error.message;
      if (!functionError.open) functionError.showModal();
    }
    return;
  }
  $("function-status").textContent = "Função atualizada para o marcador 9.";
  refresh();
});
document.addEventListener("keydown", (event) => {
  if ((!event.ctrlKey && !event.metaKey) || event.altKey) return;
  const key = event.key.toLowerCase();
  if (key === "s" && $("contour-dialog")?.open) saveCanvas($("contour-plot"),"ARMath-curvas-de-nivel");
  else if (key === "s" && !preview.hidden) savePhoto();
  else if (key === "e") toggleAxes();
  else if (key === "q") endSession();
  else return;
  event.preventDefault();
});
window.addEventListener("pagehide", endSession);

const demo = new URLSearchParams(location.search).get("demo");
if (demo !== null && /^[0-9]$/.test(demo)) {
  demonstrate("./static/marcadores/marcador_" + demo + ".png");
}
