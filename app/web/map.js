const qs = new URLSearchParams(location.search);
const access = qs.get("access") || "";
const state = { data: null, markers: [], selected: null };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const map = L.map("map", { zoomControl: false, preferCanvas: true }).setView([12.5657, 104.991], 7);
L.control.zoom({ position: "bottomright" }).addTo(map);
L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Imagery © Esri"
}).addTo(map);
L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Boundaries © Esri"
}).addTo(map);

function params() {
  const p = new URLSearchParams({ access });
  [["region","region"],["dealer","dealer"],["reportDate","report_date"],["category","category"],["product","product"],["movement","movement"]]
    .forEach(([id,key]) => { if ($(id).value) p.set(key, $(id).value); });
  return p;
}

async function loadData(preserveOptions=false) {
  $("loading").classList.remove("hidden");
  try {
    const response = await fetch(`/api/map/data?${params()}`);
    if (!response.ok) throw new Error(response.status === 401 ? "Invalid or expired map link." : "Unable to load Kobo movement data.");
    state.data = await response.json();
    if (!preserveOptions) populateOptions(state.data.options);
    renderAll();
  } catch (error) {
    $("emptyState").classList.remove("hidden");
    $("emptyState").innerHTML = `<strong>${esc(error.message)}</strong><span>Check Railway variables and reload.</span>`;
  } finally {
    $("loading").classList.add("hidden");
  }
}

function fill(id, values, placeholder) {
  const select = $(id), current = select.value;
  select.innerHTML = `<option value="">${placeholder}</option>` + values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
  if ([...select.options].some(o => o.value === current)) select.value = current;
}

function populateOptions(o) {
  fill("region", o.regions, "All regions");
  fill("dealer", o.dealers, "All dealers");
  fill("reportDate", o.dates, "All report dates");
  fill("category", o.categories, "All categories");
  fill("product", o.products, "All products");
  $("dashboardFilters").innerHTML = ["region","dealer","reportDate","category","product","movement"]
    .map(id => { const clone = $(id).cloneNode(true); clone.id = `dash-${id}`; return clone.outerHTML; }).join("");
  $("dashboardFilters").querySelectorAll("select").forEach(select => select.addEventListener("change", () => {
    $(select.id.replace("dash-","")).value = select.value; loadData(true);
  }));
}

function renderAll() {
  renderMarkers(); renderStats(); renderTable(); renderDashboard();
  const visible = state.data.rows.length, total = state.data.total_ratings;
  $("rowCount").textContent = state.data.rows_truncated
    ? `(showing ${visible.toLocaleString()} of ${total.toLocaleString()} ratings)`
    : `(${total.toLocaleString()} ratings)`;
  $("emptyState").classList.toggle("hidden", total > 0);
}

function renderMarkers() {
  state.markers.forEach(marker => marker.remove()); state.markers = [];
  const bounds = [];
  const colors = {"very-low":"#e5232e","medium":"#f5b400","very-strong":"#118a45"};
  state.data.markers.forEach(row => {
    const marker = L.circleMarker([row.latitude,row.longitude], {
      radius: 9, color: "#fff", weight: 3,
      fillColor: colors[row.band], fillOpacity: .96
    }).bindTooltip(`${esc(row.outlet_name)} · Lowest score ${row.movement}`, {direction:"top"})
      .addTo(map).on("click", () => showDetail(row));
    state.markers.push(marker); bounds.push([row.latitude,row.longitude]);
  });
  if (bounds.length) map.fitBounds(bounds, { padding:[45,45], maxZoom:16 });
  else map.setView([12.5657,104.991],7);
}

function renderStats() {
  const s = state.data.summary;
  $("stats").innerHTML = [
    ["⌂",s.outlets,"Outlets"],["●",s.ratings,"Ratings"],["↗",s.very_strong,"Very Strong"],["↘",s.very_low,"Very Low"]
  ].map(x => `<div class="stat"><b>${x[0]} ${x[1]}</b><span>${x[2]}</span></div>`).join("");
}

function showDetail(row) {
  state.selected = row;
  const destination = `https://www.google.com/maps/dir/?api=1&destination=${row.latitude},${row.longitude}&travelmode=driving`;
  $("detailCard").innerHTML = `
    <button class="close-detail" onclick="closeDetail()">×</button>
    <h2>${esc(row.outlet_name)}</h2><small>${esc(row.outlet_type)}</small>
    <div class="meta">
      <span>Phone</span><b>${esc(row.phone||"—")}</b><span>Area</span><b>${esc(row.region)} · ${esc(row.dealer)}</b>
      <span>Product</span><b>${esc(row.product)}</b><span>Product Type</span><b>${esc(row.product_type)}</b>
      <span>Category</span><b>${esc(row.category)}</b><span>Stock</span><b>${esc(row.stock_status||"—")}</b>
    </div>
    ${row.key_issue ? `<div class="issue"><b>KEY ISSUE</b><p>${esc(row.key_issue)}</p></div>` : ""}
    <div class="rating"><span>Movement Rating</span><b>${row.movement} / 10</b></div>
    <div class="meta"><span>Report Date</span><b>${esc(row.report_date||"—")}</b><span>Submitter</span><b>${esc(row.submitter||"—")}</b></div>
    <div class="actions"><a class="view-list" href="#" onclick="viewInList('${esc(row.id)}');return false">View in List</a><a class="navigate" href="${destination}" target="_blank" rel="noopener">Navigate</a></div>`;
  $("detailCard").classList.remove("hidden");
  document.querySelectorAll("tbody tr").forEach(tr => tr.classList.toggle("selected", tr.dataset.id === row.id));
}
window.closeDetail = () => $("detailCard").classList.add("hidden");
window.viewInList = id => {
  const tr = document.querySelector(`tr[data-id="${CSS.escape(id)}"]`);
  if (tr) { tr.scrollIntoView({behavior:"smooth",block:"center"}); tr.classList.add("selected"); }
};

function renderTable() {
  $("outletRows").innerHTML = state.data.rows.map(row => `<tr data-id="${esc(row.id)}">
    <td>${esc(row.outlet_name)}</td><td>${esc(row.outlet_type)}</td><td>${esc(row.phone)}</td>
    <td>${esc(row.region)}</td><td>${esc(row.dealer)}</td><td>${esc(row.product)}</td>
    <td>${esc(row.product_type)}</td><td>${esc(row.category)}</td><td>${esc(row.stock_status||"—")}</td>
    <td title="${esc(row.key_issue)}">${esc(row.key_issue||"—")}</td>
    <td><span class="score-pill ${row.band}">${row.movement}</span></td><td>${esc(row.report_date)}</td>
  </tr>`).join("");
  document.querySelectorAll("#outletRows tr").forEach((tr,i) => tr.addEventListener("click", () => showDetail(state.data.rows[i])));
}

function renderDashboard() {
  const s = state.data.summary;
  const cards = [["Outlets",s.outlets],["Product Ratings",s.ratings],["Own Products",s.own_products],["Competitors",s.competitor_products],["Own Wins (10)",s.own_wins],["With Key Issue",s.key_issues]];
  $("kpiGrid").innerHTML = cards.map(c => `<article class="kpi"><span>${c[0]}</span><b>${c[1]}</b></article>`).join("");
  renderBars("regionChart",state.data.charts.regions);
  renderBars("dealerChart",state.data.charts.dealers);
  renderBars("productChart",state.data.charts.products);
}
function renderBars(id, items) {
  const max = Math.max(1,...items.map(x=>x[1]));
  $(id).innerHTML = items.length ? items.map(([name,value]) => `<div class="bar-row"><label title="${esc(name)}">${esc(name)}</label><div class="bar"><i style="width:${value/max*100}%"></i></div><b>${value}</b></div>`).join("") : "<p>No matching data</p>";
}

function setScreen(dashboard) {
  $("mapScreen").classList.toggle("hidden",dashboard);
  $("dashboardScreen").classList.toggle("hidden",!dashboard);
  history.replaceState(null,"",`${dashboard?"/dashboard":"/map"}?access=${encodeURIComponent(access)}`);
  if (!dashboard) setTimeout(()=>map.invalidateSize(),50);
}
$("mapViewBtn").onclick = () => setScreen(false);
$("dashboardBtn").onclick = () => setScreen(true);
$("refreshBtn").onclick = () => loadData(true);
$("applyBtn").onclick = () => { loadData(true); $("filterPanel").classList.remove("open"); };
$("resetBtn").onclick = () => { ["region","dealer","reportDate","category","product","movement"].forEach(id=>$(id).value=""); loadData(true); };
$("openFilters").onclick = () => $("filterPanel").classList.add("open");
$("closeFilters").onclick = () => $("filterPanel").classList.remove("open");
$("listToggle").onclick = () => $("listPanel").classList.toggle("collapsed");
setScreen(location.pathname.includes("dashboard"));
loadData();
