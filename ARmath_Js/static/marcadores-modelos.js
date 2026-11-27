"use strict";

const featured = document.querySelector(".intro-example img");
const cards = [...document.querySelectorAll(".marker-list article")];
const rows = [...document.querySelectorAll("#marker-examples tr")];
if (featured) {
  featured.src = rows[4].querySelector("figure img").src;
}

const search = document.getElementById("marker-search");
if (search) {
  const count = document.getElementById("marker-count");
  const normalize = (text) => text.normalize("NFD").replace(/\p{Diacritic}/gu,"").toLowerCase().trim();
  const names = cards.map((card) => normalize(card.querySelector("h3").textContent));
  function filterMarkers() {
    const query = normalize(search.value);
    let visible = 0;
    for (const [id, card] of cards.entries()) {
      const matches = names[id].includes(query);
      card.hidden = rows[id].hidden = !matches;
      visible += Number(matches);
    }
    count.textContent = visible === 0 ? "Nenhum cartão encontrado."
      : visible === 1 ? "1 cartão encontrado" : visible + " cartões encontrados";
  }
  search.addEventListener("input", filterMarkers);
  filterMarkers();
}
