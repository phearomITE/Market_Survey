const qs = new URLSearchParams(location.search);
const access = qs.get("access") || "";
const state = { data: null, markers: [], areas: [], selected: null, multi: {} };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const map = L.map("map", { zoomControl: false, preferCanvas: true }).setView([12.5657, 104.991], 7);
L.control.zoom({ position: "bottomright" }).addTo(map);
const satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Imagery © Esri"
}).addTo(map);
const labels = L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Boundaries © Esri"
}).addTo(map);
const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:"© OpenStreetMap"});
L.control.layers({"Satellite":satellite,"Street":streets},{"Administrative & place labels":labels},{position:"bottomright"}).addTo(map);

function params() {
  const p = new URLSearchParams({ access });
  if (matchMedia("(max-width: 900px)").matches) p.set("mobile", "true");
  [["region","region"],["dealer","dealer"],["reportDate","report_date"],["province","province"],["district","district"],["commune","commune"],["category","category"],["product","product"],["movement","movement"]]
    .forEach(([id,key]) => selectedValues(id).forEach(value => p.append(key, value)));
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
  const select = $(id), current = selectedValues(id);
  select.dataset.placeholder = placeholder;
  select.innerHTML = `<option value="">${placeholder}</option>` + values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
  [...select.options].forEach(option => option.selected = current.includes(option.value));
  rebuildMulti(id);
}

function selectedValues(id) {
  const select = $(id);
  if (!select) return [];
  return [...select.selectedOptions].map(option => option.value).filter(Boolean);
}

function enhanceMulti(id, onChange) {
  const select = $(id);
  if (!select || state.multi[id]) return;
  select.multiple = true;
  select.classList.add("multi-source");
  const control = document.createElement("div");
  control.className = "multi-control";
  control.innerHTML = `<button type="button" class="multi-trigger"></button><div class="multi-menu"></div>`;
  select.after(control);
  state.multi[id] = { control, onChange };
  control.onclick = event => event.stopPropagation();
  control.querySelector(".multi-trigger").onclick = event => {
    event.stopPropagation();
    document.querySelectorAll(".multi-control.open").forEach(item => {
      if (item !== control) item.classList.remove("open");
    });
    control.classList.toggle("open");
  };
  rebuildMulti(id);
}

function rebuildMulti(id) {
  const entry = state.multi[id], select = $(id);
  if (!entry || !select) return;
  const menu = entry.control.querySelector(".multi-menu");
  const choices = [...select.options].filter(option => option.value);
  menu.innerHTML = choices.map(option => `
    <label><input type="checkbox" value="${esc(option.value)}" ${option.selected?"checked":""}>
    <span>${esc(option.textContent)}</span></label>`).join("") || "<p>No options</p>";
  menu.querySelectorAll("input").forEach(input => input.onchange = () => {
    const option = [...select.options].find(item => item.value === input.value);
    if (option) option.selected = input.checked;
    updateMultiLabel(id);
    if (entry.onChange) entry.onChange();
  });
  updateMultiLabel(id);
}

function updateMultiLabel(id) {
  const entry = state.multi[id], select = $(id);
  if (!entry || !select) return;
  const values = selectedValues(id);
  const labels = [...select.selectedOptions].filter(option => option.value).map(option => option.textContent);
  entry.control.querySelector(".multi-trigger").textContent =
    values.length === 0 ? (select.dataset.placeholder || "All") :
    values.length <= 2 ? labels.join(", ") : `${values.length} selected`;
}

function refreshProducts() {
  if (!state.data) return;
  const categories = selectedValues("category");
  const mapping = state.data.options.products_by_category || {};
  const products = categories.length
    ? [...new Set(categories.flatMap(category => mapping[category] || []))].sort()
    : state.data.options.products;
  fill("product", products, "All products");
}

function populateOptions(o) {
  fill("region", o.regions, "All regions");
  fill("dealer", o.dealers, "All dealers");
  fill("reportDate", o.dates, "All report dates");
  fill("province", o.provinces, "All provinces");
  fill("district", o.districts, "All districts");
  fill("commune", o.communes, "All communes");
  fill("category", o.categories, "All categories");
  fill("product", o.products, "All products");
  const filterLabels = {
    region:"Region", dealer:"Dealer", reportDate:"Report Date",
    province:"Province / Capital", district:"District / Khan",
    commune:"Commune / Sangkat", category:"Product Category",
    product:"Product", movement:"Movement Score"
  };
  $("dashboardFilters").innerHTML = ["region","dealer","reportDate","province","district","commune","category","product","movement"]
    .map(id => {
      const clone = $(id).cloneNode(true);
      clone.id = `dash-${id}`;
      return `<label><span>${filterLabels[id]}</span>${clone.outerHTML}</label>`;
    }).join("");
  $("dashboardFilters").querySelectorAll("select").forEach(select => {
    const sourceId = select.id.replace("dash-","");
    enhanceMulti(select.id, () => {
      const source = $(sourceId);
      const selected = selectedValues(select.id);
      [...source.options].forEach(option => option.selected = selected.includes(option.value));
      updateMultiLabel(sourceId);
      if (sourceId === "category") refreshProducts();
      loadData(true);
    });
  });
}

function renderAll() {
  renderMarkers(); renderStats(); renderDashboard();
  const total = state.data.total_ratings;
  $("emptyState").classList.toggle("hidden", total > 0);
}

function renderMarkers() {
  state.markers.forEach(marker => marker.remove()); state.markers = [];
  state.areas.forEach(area => area.remove()); state.areas = [];
  const bounds = [];
  const rows = state.data.markers;
  let index = 0;
  const renderBatch = () => {
    const end = Math.min(index + 80, rows.length);
    for (; index < end; index += 1) {
      const row = rows[index];
      const areaColor = row.band === "very-low" ? "#e5232e" : row.band === "medium" ? "#f5b400" : "#118a45";
      const area = L.circle([row.latitude,row.longitude], {
        radius: matchMedia("(max-width: 900px)").matches ? 2200 : 1500,
        stroke: false, fillColor: areaColor, fillOpacity: 0.14,
        interactive: false,
      }).addTo(map);
      const marker = L.marker([row.latitude,row.longitude], {
        icon: L.divIcon({
          className: "movement-marker-wrap",
          html: `<span class="score-marker ${row.band}">${row.movement}</span>`,
          iconSize: [32,32], iconAnchor: [16,16],
        }),
        riseOnHover: true,
      }).bindTooltip(`${esc(row.outlet_name)} · Movement ${row.movement}`, {direction:"top"})
        .addTo(map).on("click", () => showDetail(row));
      state.markers.push(marker); bounds.push([row.latitude,row.longitude]);
      state.areas.push(area);
    }
    if (index < rows.length) requestAnimationFrame(renderBatch);
    else if (bounds.length) map.fitBounds(bounds, { padding:[45,45], maxZoom:16 });
    else map.setView([12.5657,104.991],7);
  };
  requestAnimationFrame(renderBatch);
}

function renderStats() {
  const s = state.data.summary;
  $("stats").innerHTML = [
    ["⌂",s.outlets,"Outlets"],
    ["R",s.regions,"Region"],
    ["D",s.dealers,"Dealer"],
    ["P",s.provinces,"Province"],
    ["↗",s.very_strong,"Very Strong"],
    ["↘",s.very_low,"Very Low"]
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
      <span>Location</span><b>${esc([row.province,row.district,row.commune,row.village].filter(Boolean).join(" · ")||"Pending GPS conversion")}</b>
      <span>Category</span><b>${esc(row.category)}</b><span>Stock</span><b>${esc(row.stock_status||"—")}</b>
    </div>
    ${row.key_issue ? `<div class="issue"><b>KEY ISSUE</b><p>${esc(row.key_issue)}</p></div>` : ""}
    <div class="rating"><span>Movement Rating</span><b>${row.movement} / 10</b></div>
    ${row.product_ratings?.length?`<div class="product-ratings"><b>ALL PRODUCT RATINGS (${row.product_ratings.length})</b>${row.product_ratings.map(item=>`<button onclick="selectProductRating('${esc(item.id)}')"><span>${esc(item.product)}</span><i class="score-pill ${item.band}">${item.movement}</i></button>`).join("")}</div>`:""}
    <div class="meta"><span>Report Date</span><b>${esc(row.report_date||"—")}</b><span>Submitter</span><b>${esc(row.submitter||"—")}</b></div>
    <div class="actions"><a class="navigate" href="${destination}" target="_blank" rel="noopener">Navigate</a>${state.data.can_edit?'<button class="edit-rating" onclick="openEdit();return false">✎ Edit Stock, Movement & Key Issue</button>':''}</div>`;
  $("detailCard").classList.remove("hidden");
  document.querySelectorAll("tbody tr").forEach(tr => tr.classList.toggle("selected", tr.dataset.id === row.id));
  if (!row.product_ratings) loadOutletRatings(row);
}
async function loadOutletRatings(row) {
  try {
    const response=await fetch(`/api/map/outlets/${encodeURIComponent(row.submission_id)}/ratings?access=${encodeURIComponent(access)}`);
    if(!response.ok)return;
    const payload=await response.json();
    if(state.selected?.submission_id!==row.submission_id)return;
    row.product_ratings=payload.rows;
    showDetail(row);
  } catch (_) {}
}
window.closeDetail = () => $("detailCard").classList.add("hidden");
window.openEdit = () => {
  const row=state.selected;if(!row)return;
  $("editTitle").textContent=`${row.outlet_name} · ${row.product}`;
  $("editMovement").value=row.movement;$("editStock").value=row.stock_status||"";$("editIssue").value=row.key_issue||"";
  $("editDialog").showModal();
};
window.selectProductRating=id=>{
  const row=(state.selected?.product_ratings||[]).find(item=>item.id===id);
  if(!row)return;
  const full=state.data.rows.find(item=>item.id===id)||{...state.selected,...row,product_ratings:state.selected.product_ratings};
  showDetail(full);
};

function renderDashboard() {
  const s = state.data.summary;
  const cards = [["Total Outlets",s.outlets],["Product Ratings",s.ratings],["Own Product Ratings",s.own_products],["Competitor Ratings",s.competitor_products],["Own Wins (10)",s.own_wins],["Competitor Wins (10)",s.competitor_wins],["Very Low (1–4)",s.very_low],["Very Strong (9–10)",s.very_strong],["With Key Issue",s.key_issues]];
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
  $("mapViewBtn").classList.toggle("active",!dashboard);
  $("dashboardBtn").classList.toggle("active",dashboard);
  history.replaceState(null,"",`${dashboard?"/dashboard":"/map"}?access=${encodeURIComponent(access)}`);
  if (!dashboard) setTimeout(()=>map.invalidateSize(),50);
}
$("mapViewBtn").onclick = () => setScreen(false);
$("dashboardBtn").onclick = () => setScreen(true);
$("refreshBtn").onclick = () => loadData(true);
$("applyBtn").onclick = () => { loadData(true); $("filterPanel").classList.remove("open"); };
$("resetBtn").onclick = () => {
  ["region","dealer","reportDate","province","district","commune","category","product","movement"].forEach(id => {
    [...$(id).options].forEach(option => option.selected = false);
    rebuildMulti(id);
  });
  loadData(true);
};
$("openFilters").onclick = () => $("filterPanel").classList.add("open");
$("closeFilters").onclick = () => $("filterPanel").classList.remove("open");
["region","dealer","reportDate","province","district","commune","category","product","movement"]
  .forEach(id => enhanceMulti(id, id === "category" ? refreshProducts : null));
document.addEventListener("click", () => document.querySelectorAll(".multi-control.open").forEach(item => item.classList.remove("open")));
setScreen(location.pathname.includes("dashboard"));
loadData();
$("closeEdit").onclick=$("cancelEdit").onclick=()=>$("editDialog").close();
$("editForm").onsubmit=async event=>{
  event.preventDefault();const movement=Number($("editMovement").value);
  if(!Number.isInteger(movement)||movement<0||movement>10){alert("Movement must be a whole number from 0 to 10.");return}
  $("loading").classList.remove("hidden");
  const response=await fetch(`/api/map/ratings/${encodeURIComponent(state.selected.id)}?access=${encodeURIComponent(access)}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({movement,stock_status:$("editStock").value,key_issue:$("editIssue").value})});
  $("loading").classList.add("hidden");
  if(!response.ok){alert("Update failed. Please reload and try again.");return}
  $("editDialog").close();await loadData(true);
};
