"use strict";

const markerList = document.querySelector(".marker-list");
const examples = document.getElementById("marker-examples");
const previewCanvas = document.createElement("canvas");
previewCanvas.width = 400;
previewCanvas.height = 300;
const previewContext = previewCanvas.getContext("2d");
const exampleCorners = [[134,156],[268,143],[292,224],[105,239]];
const customExample = surfaces.custom("x+y");
for (const [id, [name]] of surfaces.catalog.entries()) {
  const url = "./static/marcadores/marcador_" + id + ".png";
  const card = document.createElement("article");
  card.innerHTML = `<h3></h3>
    <img src="${url}" alt="Marcador ArUco ${id}" width="176" height="176">
    <div class="card-actions">
      <button class="primary" type="button">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8V3h12v5M6 17H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6zM18 11h1"/></svg>
        Imprimir
      </button>
      <a class="download-marker" href="${url}" download aria-label="Baixar PNG do marcador ${id}">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M4 16v4h16v-4"/></svg>
        Baixar PNG
      </a>
    </div>`;
  card.querySelector("h3").textContent = id + " · " + name;
  const print = card.querySelector("button");
  const clearPrintSelection = () => {
    delete markerList.dataset.printing;
    delete card.dataset.selected;
    for (const button of markerList.querySelectorAll("button")) button.disabled = false;
  };
  print.setAttribute("aria-label", "Imprimir marcador " + id);
  print.addEventListener("click", async () => {
    const feedback = document.getElementById("print-status");
    feedback.hidden = true;
    for (const button of markerList.querySelectorAll("button")) button.disabled = true;
    try {
      await card.querySelector("img").decode();
      markerList.dataset.printing = "";
      card.dataset.selected = "";
      window.addEventListener("afterprint", clearPrintSelection, {once: true});
      window.print();
    } catch {
      window.removeEventListener("afterprint", clearPrintSelection);
      clearPrintSelection();
      feedback.textContent = "Não foi possível imprimir o marcador " + id + ".";
      feedback.hidden = false;
    }
  });
  markerList.append(card);

  const row = examples.insertRow();
  row.innerHTML = `<th scope="row">
    <img src="${url}" alt="Marcador ArUco ${id}" width="112" height="112" loading="lazy">
    <span>Cartão ${id}</span>
  </th>
  <td>
    <figure>
      <img alt="" width="400" height="300" loading="lazy">
      <figcaption></figcaption>
    </figure>
  </td>`;
  previewContext.clearRect(0,0,previewCanvas.width,previewCanvas.height);
  surfaces.draw(previewContext, [{id,corners:exampleCorners}], {
    scale: id < 2 ? .62 : .85, angles: [0,0,0],
  }, customExample);
  row.querySelector("figure img").src = previewCanvas.toDataURL("image/png");
  row.querySelector("figcaption").textContent = id === 9 ? name + " · f(x,y) = x + y" : name;
}
