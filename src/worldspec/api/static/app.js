"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, html = "") => {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (html) e.innerHTML = html;
  return e;
};
const SVGNS = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}, text = "") => {
  const e = document.createElementNS(SVGNS, tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (text) e.textContent = text;
  return e;
};
const api = async (path, opts) => {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((body.detail && body.detail.message) || r.statusText);
  return body;
};

const SAMPLE_CONTEXT = {
  transition: "COBOLToJava",
  entities: {
    "SETTLEMENT.VSAM": { type: "Dataset", state: { lockMode: "none", writeAuthority: "GS-COBOL", activeWriters: 2, unreconciledItems: 0 } },
    "GS-COBOL": { type: "Application", state: { validationStatus: "passed", criticality: "systemic", rollbackWindowHours: 24 } },
    "GS-Java": { type: "Application", state: { validationStatus: "pending", lifecycle: "active", criticality: "high", rollbackWindowHours: 24 } },
    "JOB.SETTLE.020": { type: "BatchJob", state: { slaMinutes: 90, durationMinutes: 60 } }
  },
  relationships: [{ name: "writes", from: "JOB.SETTLE.020", to: "SETTLEMENT.VSAM" }],
  bindings: { dataset: "SETTLEMENT.VSAM", source: "GS-COBOL", target: "GS-Java" }
};

const stateName = { model: null, models: [], lastEvidence: null };

// --------------------------- tabs ----------------------------------------- //
document.querySelectorAll("#tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "graph") renderGraph();
  });
});

// --------------------------- bootstrap ------------------------------------ //
async function init() {
  try {
    const h = await api("/health");
    const llm = h.llm || {};
    const status = $("#llmStatus");
    if (llm.provider) {
      status.innerHTML = `LLM provider: <b>${llm.provider}</b> (${llm.model}). "use LLM" will produce a tailored model.`;
      $("#useLLM").checked = true;
    } else {
      status.innerHTML = '<span class="badge high">no LLM configured</span> ' +
        'builds will use the offline heuristic. Add a key to <b>.env</b> and restart the server.';
    }
  } catch (e) { /* health is best-effort */ }
  stateName.models = await api("/models");
  const sel = $("#modelSelect");
  sel.innerHTML = "";
  stateName.models.forEach((m) => sel.appendChild(el("option", { value: m.name }, m.name)));
  sel.addEventListener("change", () => selectModel(sel.value));
  $("#stateContext").value = JSON.stringify(SAMPLE_CONTEXT, null, 2);
  $("#simContext").value = JSON.stringify(SAMPLE_CONTEXT, null, 2);
  if (stateName.models.length) {
    selectModel(stateName.models[0].name);
  } else {
    $("#browser").innerHTML =
      `<div class="card"><h3>No models loaded</h3>
        <div class="kv">The server started without any models registered. Start it from the
        repository root (the folder containing <b>models/</b>):</div>
        <pre class="mono">cd path/to/worldspec
worldspec serve</pre>
        <div class="kv">…or launch with <b>--models &lt;dir&gt;</b>, or register one via
        <b>POST /models/register</b>.</div></div>`;
  }
}

async function selectModel(name) {
  stateName.model = name;
  const m = await api(`/models/${name}`);
  stateName.detail = m;
  renderBrowser(m);
  populateTransitions(m);
  // Pre-fill the inspector/simulator with a context that matches THIS model.
  const ctx = buildSampleContext(m);
  $("#stateContext").value = JSON.stringify(ctx.inspect, null, 2);
  $("#simContext").value = JSON.stringify(ctx.simulate, null, 2);
  renderGraph();
}

// Build a skeleton context (instances + sensible default state) for a model, so
// the State Inspector / Simulator always match the selected model's entity types.
function defaultFor(decl) {
  switch (decl.type) {
    case "enum": return (decl.values && decl.values[0]) || "";
    case "int": return 0;
    case "float": return 0.0;
    case "bool": return false;
    default: return "";   // string, datetime, ref
  }
}

function buildSampleContext(m) {
  const dims = {};   // entityName -> {field: decl}
  (m.states || []).forEach((s) => { dims[s.entity] = Object.assign(dims[s.entity] || {}, s.dimensions || {}); });

  const entities = {};
  const idForType = {};
  (m.entities || []).forEach((e) => {
    const id = e.name + "1";
    idForType[e.name] = id;
    const idents = new Set(e.identity || []);
    const state = {};
    // identity fields must be non-empty; use the instance id as a placeholder.
    Object.entries(e.properties || {}).forEach(([k, d]) => { state[k] = idents.has(k) ? id : defaultFor(d); });
    Object.entries(dims[e.name] || {}).forEach(([k, d]) => { state[k] = defaultFor(d); });
    entities[id] = { type: e.name, state };
  });

  const inspect = { entities };

  // Best-effort simulator context: first transition + bindings by input type.
  const simulate = { entities };
  const t = (m.transitions || [])[0];
  if (t) {
    simulate.transition = t.name;
    const action = (m.actions || []).find((a) => a.name === t.action);
    const bindings = {};
    if (action) {
      Object.entries(action.inputs || {}).forEach(([inName, decl]) => {
        bindings[inName] = idForType[decl.target] || "";
      });
    }
    simulate.bindings = bindings;
  }
  return { inspect, simulate };
}

// --------------------------- 1. Model Browser ----------------------------- //
function renderBrowser(m) {
  const host = $("#browser");
  host.innerHTML = "";
  const counts = el("div", { class: "counts" });
  [["entity", m.entities], ["relationship", m.relationships], ["state", m.states],
   ["invariant", m.invariants], ["action", m.actions], ["transition", m.transitions]]
    .forEach(([k, arr]) => counts.appendChild(el("span", { class: "chip" }, `${k} <b>${arr.length}</b>`)));
  host.appendChild(counts);

  const cards = el("div", { class: "cards" });
  m.invariants.forEach((inv) => {
    const sev = inv.severity === "critical" ? "crit" : (inv.severity === "high" ? "high" : "");
    cards.appendChild(el("div", { class: "card" },
      `<h3>${inv.name} <span class="badge ${sev}">${inv.severity}</span></h3>
       <div class="kv">applies to <b>${inv.targetType}</b></div>
       <div class="kv">on violation: <b>${inv.onViolation}</b></div>`));
  });
  m.transitions.forEach((t) => {
    cards.appendChild(el("div", { class: "card" },
      `<h3>${t.name} <span class="badge low">transition</span></h3>
       <div class="kv">action <b>${t.action}</b></div>
       <div class="kv">preserves: ${t.preserves.join(", ") || "—"}</div>`));
  });
  m.entities.forEach((e) => {
    cards.appendChild(el("div", { class: "card" },
      `<h3>${e.name} <span class="badge low">entity</span></h3>
       <div class="kv">${e.description || ""}</div>
       <div class="kv">properties: ${Object.keys(e.properties || {}).join(", ")}</div>`));
  });
  host.appendChild(cards);
}

// --------------------------- 2. Dependency Graph -------------------------- //
async function renderGraph() {
  if (!stateName.model) return;
  const g = await api(`/models/${stateName.model}/graph`);
  const host = $("#graphHost");
  host.innerHTML = "";
  const W = Math.max(640, host.clientWidth || 900), H = 560, cx = W / 2, cy = H / 2;
  const R = Math.min(cx, cy) - 80;
  const n = g.nodes.length || 1;
  const pos = {};
  g.nodes.forEach((node, i) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[node.id] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
  // edges
  g.edges.forEach((e) => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    svg.appendChild(svgEl("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: "#2b3a4d", "stroke-width": "1.5" }));
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    svg.appendChild(svgEl("text", { x: mx, y: my, "text-anchor": "middle", fill: "#6f8298" }, e.type));
  });
  // nodes
  g.nodes.forEach((node) => {
    const p = pos[node.id];
    svg.appendChild(svgEl("circle", { cx: p.x, cy: p.y, r: "8", fill: "#00b9ff" }));
    svg.appendChild(svgEl("text", { x: p.x + 12, y: p.y + 4, fill: "#e6edf3" }, node.id));
  });
  host.appendChild(svg);
}

// --------------------------- 3. State Inspector --------------------------- //
$("#inspectBtn").addEventListener("click", async () => {
  const out = $("#stateResult");
  out.innerHTML = "";
  let context;
  try { context = JSON.parse($("#stateContext").value); }
  catch (e) { out.innerHTML = `<p class="err">Invalid JSON: ${e.message}</p>`; return; }
  try {
    const res = await api("/world/inspect", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: stateName.model, context })
    });
    const cards = el("div", { class: "cards" });
    res.entities.forEach((e) => {
      const checks = e.invariants.map((c) =>
        `<li>${c.passed ? '<span class="badge ok">holds</span>' : '<span class="badge bad">VIOLATED</span>'} ${c.invariant} <span class="kv">— ${c.reason}</span></li>`).join("");
      cards.appendChild(el("div", { class: "card" },
        `<h3>${e.id} <span class="badge low">${e.type}</span></h3>
         <div class="kv">state: ${JSON.stringify(e.state)}</div>
         <div class="kv">impact: ${e.impact.join(", ") || "—"}</div>
         <ul class="clean">${checks || '<li class="kv">no invariants for this type</li>'}</ul>`));
    });
    out.appendChild(cards);
  } catch (e) { out.innerHTML = `<p class="err">${e.message}</p>`; }
});

// --------------------------- 4. Transition Simulator ---------------------- //
function populateTransitions(m) {
  const sel = $("#transitionSelect");
  sel.innerHTML = "";
  const hasTransitions = (m.transitions || []).length > 0;
  m.transitions.forEach((t) => sel.appendChild(el("option", { value: t.name }, t.name)));
  $("#simulateBtn").disabled = !hasTransitions;
  const out = $("#simResult");
  if (!hasTransitions) {
    sel.appendChild(el("option", { value: "" }, "(no transitions in this model)"));
    out.innerHTML =
      `<p class="hint">This model defines no <b>transitions</b> (it has ${m.invariants.length} ` +
      `invariant(s) but no actions/transitions), so there is nothing to simulate. ` +
      `Use the <b>State Inspector</b> to check invariants against observed state, or ` +
      `rebuild the model so it includes actions and transitions (see note below).</p>`;
  } else {
    out.innerHTML = "";
  }
}
$("#loadSampleBtn").addEventListener("click", () => {
  const ctx = stateName.detail ? buildSampleContext(stateName.detail).simulate : SAMPLE_CONTEXT;
  $("#simContext").value = JSON.stringify(ctx, null, 2);
});
$("#simulateBtn").addEventListener("click", async () => {
  const out = $("#simResult");
  out.innerHTML = "";
  const transition = $("#transitionSelect").value;
  if (!transition) {
    out.innerHTML = '<p class="err">This model has no transition to simulate. Pick a model that ' +
      'defines transitions, or rebuild this one to include actions and transitions.</p>';
    return;
  }
  let context;
  try { context = JSON.parse($("#simContext").value); }
  catch (e) { out.innerHTML = `<p class="err">Invalid JSON: ${e.message}</p>`; return; }
  try {
    const res = await api("/transitions/simulate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: stateName.model, transition, context })
    });
    stateName.lastEvidence = res.evidence;
    renderEvidence(res.evidence);
    const vcls = res.allowed ? "allowed" : "blocked";
    const verdict = res.allowed ? "ALLOWED" : "BLOCKED";
    const viol = res.violations.map((v) =>
      `<li><span class="badge bad">${v.severity}</span> ${v.reason}</li>`).join("");
    const traj = res.recommendedTrajectory.map((s) => `<span class="step">${s}</span>`).join('<span class="arrow">→</span>');
    const risk = Object.entries(res.riskComponents).map(([k, v]) => `<li>${k}: <b>${v}</b></li>`).join("");
    out.innerHTML =
      `<div class="verdict ${vcls}">${res.transition} → ${verdict} <span class="badge ${res.riskLevel}">risk: ${res.riskLevel}</span></div>
       <div class="kv">action: <b>${res.action}</b></div>
       <h3>Violations</h3><ul class="clean">${viol || '<li class="kv">none</li>'}</ul>
       <h3>Preserved</h3><div class="kv">${res.passed.join(", ") || "—"}</div>
       <h3>Impacted entities</h3><div class="kv">${res.impactedEntities.join(", ") || "—"}</div>
       <h3>Recommended trajectory</h3><div class="traj">${traj || '<span class="kv">—</span>'}</div>
       <h3>Risk breakdown</h3><ul class="clean">${risk}</ul>`;
  } catch (e) { out.innerHTML = `<p class="err">${e.message}</p>`; }
});

// --------------------------- 0. Create Model ------------------------------ //
$("#buildBtn").addEventListener("click", async () => {
  const out = $("#buildResult");
  const repo = $("#repoInput").value.trim();
  const name = $("#repoName").value.trim();
  if (!repo || !name) { out.innerHTML = '<p class="err">Provide a repository and a model name.</p>'; return; }
  out.innerHTML = '<p class="hint">Building… cloning + surveying the repository.</p>';
  try {
    const res = await api("/models/build", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo, name, useLLM: $("#useLLM").checked })
    });
    const diags = (res.diagnostics || []).map((d) =>
      `<li><span class="badge ${d.severity === 'error' ? 'bad' : 'high'}">${d.severity}</span> ${d.code}: ${d.message}</li>`).join("");
    out.innerHTML =
      `<div class="card">
         <h3>${res.name} <span class="badge ${res.ok ? 'ok' : 'bad'}">${res.ok ? 'valid' : 'invalid'}</span>
             <span class="badge low">${res.method}</span></h3>
         <div class="kv">stack: <b>${res.survey ? res.survey.stack : '?'}</b>,
              units: <b>${res.survey ? res.survey.unitCount : 0}</b>,
              registered: <b>${res.registered}</b></div>
         ${res.note ? `<div class="kv">⚠ ${res.note}</div>` : ""}
         ${diags ? `<h3>Diagnostics</h3><ul class="clean">${diags}</ul>` : ""}
         <h3>Generated model</h3>
         <pre class="mono">${(res.modelYaml || "").replace(/</g, "&lt;")}</pre>
       </div>`;
    if (res.registered) {
      await refreshModels();
      $("#modelSelect").value = res.name;
      selectModel(res.name);
    }
  } catch (e) { out.innerHTML = `<p class="err">${e.message}</p>`; }
});

async function refreshModels() {
  stateName.models = await api("/models");
  const sel = $("#modelSelect");
  sel.innerHTML = "";
  stateName.models.forEach((m) => sel.appendChild(el("option", { value: m.name }, m.name)));
}

// --------------------------- 5. Evidence ---------------------------------- //
function renderEvidence(ev) {
  const out = $("#evidenceResult");
  if (!ev) { out.innerHTML = '<p class="hint">No evidence yet.</p>'; return; }
  out.innerHTML =
    `<div class="card">
       <h3>${ev.decisionId} <span class="badge low">confidence ${ev.confidence}</span></h3>
       <div class="kv">model <b>${ev.model}</b> @ IR ${ev.irVersion} · ${ev.timestamp || ""}</div>
       <div class="kv">proposed: <b>${ev.proposedTransition}</b> via <b>${ev.proposedAction}</b></div>
       <h3>Invariants failed</h3><div class="kv">${ev.invariantsFailed.join(", ") || "none"}</div>
       <h3>Invariants passed</h3><div class="kv">${ev.invariantsPassed.join(", ") || "none"}</div>
       <h3>Assumptions</h3><ul class="clean">${ev.assumptions.map((a) => `<li class="kv">${a}</li>`).join("")}</ul>
       <h3>Recommended next step</h3><div class="kv"><b>${ev.recommendedNextStep || "proceed"}</b></div>
     </div>`;
}
$("#evidenceBtn").addEventListener("click", async () => {
  const id = $("#decisionInput").value.trim();
  if (!id) return;
  try { renderEvidence(await api(`/evidence/${id}`)); }
  catch (e) { $("#evidenceResult").innerHTML = `<p class="err">${e.message}</p>`; }
});

init().catch((e) => { document.body.appendChild(el("p", { class: "err" }, "Init failed: " + e.message)); });
