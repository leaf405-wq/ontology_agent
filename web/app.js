const graphEl = document.getElementById("graph");
const factsEl = document.getElementById("facts");
const sqlEl = document.getElementById("sql");
const interpEl = document.getElementById("interp");
const qEl = document.getElementById("q");
let network;

function drawGraph(graph, highlights = { entities: [], rels: [] }) {
  const nodes = new vis.DataSet(
    (graph.nodes || []).map((n) => ({
      id: n.id,
      label: `${n.icon || ""} ${n.label}`,
      color: {
        background: n.color || "#4aa3ff",
        border: highlights.entities.includes(n.id) ? "#fff" : "#0b1220",
        highlight: { background: n.color, border: "#fff" },
      },
      font: { color: "#fff" },
      shape: "dot",
      size: highlights.entities.includes(n.id) ? 28 : 20,
      title: (n.properties || []).join(", "),
    }))
  );
  const edges = new vis.DataSet(
    (graph.edges || []).map((e) => ({
      id: e.id,
      from: e.from,
      to: e.to,
      label: e.label,
      arrows: "to",
      color: { color: highlights.rels.includes(e.id) ? "#7dd3fc" : "#6b7c99" },
      width: highlights.rels.includes(e.id) ? 2.5 : 1,
      font: { color: "#c5d4ea", size: 11, strokeWidth: 0 },
    }))
  );
  network = new vis.Network(graphEl, { nodes, edges }, {
    physics: { solver: "forceAtlas2Based", stabilization: { iterations: 120 } },
    interaction: { hover: true },
  });
}

async function loadOntology() {
  const res = await fetch("/api/ontology");
  const data = await res.json();
  document.getElementById("ont-name").textContent = data.ontology.name;
  document.getElementById("dict").value = JSON.stringify(data.ontology, null, 2);
  drawGraph(data.graph);
}

async function runQuery(q) {
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q }),
  });
  const data = await res.json();
  interpEl.textContent = data.interpretation || "";
  sqlEl.textContent = (data.sql && data.sql.length ? data.sql.join("\n\n") : "-- 无 SQL");
  factsEl.innerHTML = "";
  if (!data.facts || !data.facts.length) {
    factsEl.innerHTML = '<p class="hint">没有匹配到事实行。</p>';
  } else {
    for (const f of data.facts) {
      const card = document.createElement("div");
      card.className = "card";
      const value = typeof f.value === "object" ? JSON.stringify(f.value) : f.value;
      card.innerHTML = `<b>${f.meaning || f.entity}</b><div>${f.name} <small>(${f.id})</small></div><div class="v">${value}${f.unit ? " " + f.unit : ""}</div><small>${f.metric || ""}</small>`;
      factsEl.appendChild(card);
    }
  }
  drawGraph(data.subgraph || data.fullGraph, {
    entities: data.highlightEntities || [],
    rels: data.highlightRelationships || [],
  });
}

document.getElementById("prompt").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = qEl.value.trim();
  if (q) runQuery(q);
});

document.getElementById("examples").addEventListener("click", (e) => {
  if (e.target.tagName === "LI") {
    qEl.value = e.target.textContent;
    runQuery(qEl.value);
  }
});

document.getElementById("reload").addEventListener("click", async () => {
  const payload = JSON.parse(document.getElementById("dict").value);
  const res = await fetch("/api/dictionary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  document.getElementById("ont-name").textContent = data.name;
  drawGraph(data.graph);
  interpEl.textContent = "已根据新数据字典重生本体图。";
});

loadOntology().catch((err) => {
  interpEl.textContent = "无法加载本体：" + err;
});
