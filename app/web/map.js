"use strict";
const query=new URLSearchParams(location.search),access=query.get("access")||"",isPhone=matchMedia("(max-width: 900px)").matches;
const $=id=>document.getElementById(id),esc=value=>String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const state={data:null,selected:null,aborter:null};
// Draw score text in the same canvas as each circle. Avoiding hundreds of
// permanent HTML tooltips makes pinch-zoom and panning much smoother on phones.
const updateCircle=L.Canvas.prototype._updateCircle;
L.Canvas.include({_updateCircle(layer){
  updateCircle.call(this,layer);const label=layer.options.scoreLabel;
  if(label===undefined||label===null||!layer._point)return;
  const ctx=this._ctx;ctx.save();ctx.font=`700 ${isPhone?11:12}px system-ui,sans-serif`;ctx.textAlign="center";ctx.textBaseline="middle";ctx.lineWidth=2;ctx.strokeStyle="rgba(0,0,0,.45)";ctx.fillStyle="#fff";ctx.strokeText(String(label),layer._point.x,layer._point.y);ctx.fillText(String(label),layer._point.x,layer._point.y);ctx.restore();
}});
const map=L.map("map",{zoomControl:false,preferCanvas:true,zoomAnimation:!isPhone,fadeAnimation:false,markerZoomAnimation:false,inertia:!isPhone,wheelDebounceTime:35,wheelPxPerZoomLevel:90}).setView([12.5657,104.991],7);
L.control.zoom({position:"bottomright"}).addTo(map);
const satellite=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{maxZoom:19,attribution:"Imagery © Esri",updateWhenIdle:true,updateWhenZooming:false,keepBuffer:isPhone?1:2,detectRetina:false}).addTo(map);
const labels=L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",{maxZoom:19,attribution:"Boundaries © Esri",updateWhenIdle:true,updateWhenZooming:false,keepBuffer:1,detectRetina:false}).addTo(map);
const street=L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:"© OpenStreetMap",updateWhenIdle:true,updateWhenZooming:false,keepBuffer:1,detectRetina:false});
const markerRenderer=L.canvas({padding:.25,tolerance:8}),movementGroup=L.layerGroup().addTo(map);
const scoreColor=score=>score<=4?"#e42431":score<=8?"#f4ae00":"#138b48";

// Canvas circles are much faster than hundreds of HTML markers during pan/zoom.
function addMarker(row){
  const marker=L.circleMarker([row.latitude,row.longitude],{renderer:markerRenderer,radius:isPhone?12:13,color:"#fff",weight:3,fillColor:scoreColor(row.movement),fillOpacity:.98,bubblingMouseEvents:false,scoreLabel:row.movement});
  marker.on("click",()=>showDetail(row)); marker.addTo(movementGroup);
}
function selected(id){const element=$(id);return element&&element.value?[element.value]:[]}
function requestParams(){
  const params=new URLSearchParams({access}); if(isPhone)params.set("mobile","true");
  [["region","region"],["dealer","dealer"],["reportDate","report_date"],["province","province"],["district","district"],["commune","commune"],["category","category"],["product","product"],["movement","movement"]].forEach(([id,key])=>selected(id).forEach(value=>params.append(key,value)));
  return params;
}
async function loadData({preserveOptions=false,preserveView=false}={}){
  if(state.aborter)state.aborter.abort(); state.aborter=new AbortController(); $("loading").classList.remove("hidden"); $("emptyState").classList.add("hidden");
  try{
    const response=await fetch(`/api/map/data?${requestParams()}`,{signal:state.aborter.signal,headers:{Accept:"application/json"}});
    if(!response.ok)throw new Error(response.status===401?"Invalid or expired map link.":"Unable to load movement data.");
    state.data=await response.json(); if(!preserveOptions)populateOptions(state.data.options); renderMap(preserveView); renderStats();
    const now=new Date(); $("syncStatus").innerHTML=`<i></i><span>Synced ${now.toLocaleDateString()} · ${now.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}</span>`;
  }catch(error){if(error.name==="AbortError")return;$("emptyState").classList.remove("hidden");$("emptyState").innerHTML=`<strong>${esc(error.message)}</strong><span>Check the link or try again.</span>`}
  finally{$("loading").classList.add("hidden")}
}
function fill(id,values,placeholder){const element=$(id),current=element.value;element.innerHTML=`<option value="">${esc(placeholder)}</option>`+values.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("");if([...element.options].some(option=>option.value===current))element.value=current}
function populateOptions(options){fill("region",options.regions,"All regions");fill("dealer",options.dealers,"All dealers");fill("reportDate",options.dates,"All report dates");fill("province",options.provinces,"All provinces");fill("district",options.districts,"All districts");fill("commune",options.communes,"All communes");fill("category",options.categories,"All categories");fill("product",options.products,"All products")}
function updateProducts(){if(!state.data)return;const category=$("category").value,products=category?(state.data.options.products_by_category[category]||[]):state.data.options.products;fill("product",products,"All products")}
function renderMap(preserveView){
  movementGroup.clearLayers();closeDetail();const rows=state.data.markers||[];rows.forEach(addMarker);$("emptyState").classList.toggle("hidden",rows.length>0);
  if(!preserveView&&rows.length){map.fitBounds(L.latLngBounds(rows.map(row=>[row.latitude,row.longitude])),{padding:isPhone?[28,28]:[55,55],maxZoom:15,animate:false})}
  else if(!rows.length&&!preserveView)map.setView([12.5657,104.991],7,{animate:false});
}
function renderStats(){const s=state.data.summary,cards=[["⌂",s.outlets,"Outlets","outlet"],["●",s.medium,"Medium","medium"],["↗",s.very_strong,"Very Strong","strong"],["↘",s.very_low,"Very Low","weak"]];$("stats").innerHTML=cards.map(([icon,value,label,kind])=>`<div class="stat"><i class="stat-icon ${kind}">${icon}</i><b>${value}</b><span>${label}</span></div>`).join("")}
async function showDetail(row){
  state.selected=row;renderDetail(row,null);
  try{const response=await fetch(`/api/map/outlets/${encodeURIComponent(row.submission_id)}/ratings?${requestParams()}`);if(!response.ok||state.selected!==row)return;const payload=await response.json();renderDetail(row,payload.rows||[])}catch(_){/* marker details remain usable */}
}
function renderDetail(row,ratings){
  const destination=`https://www.google.com/maps/dir/?api=1&destination=${row.latitude},${row.longitude}&travelmode=driving`,color=scoreColor(row.movement),locationText=[row.province,row.district,row.commune,row.village].filter(Boolean).join(" · ")||row.location||"Location pending";
  $("detailCard").innerHTML=`<button class="close-detail" type="button" aria-label="Close details">×</button><h2>${esc(row.outlet_name)}</h2><small>${esc(row.outlet_type||"Outlet")}</small><div class="meta"><span>Phone</span><b>${esc(row.phone||"—")}</b><span>Area</span><b>${esc(row.region)} · ${esc(row.dealer)}</b><span>Product</span><b>${esc(row.product)}</b><span>Category</span><b>${esc(row.category)}</b><span>Location</span><b>${esc(locationText)}</b><span>Stock</span><b>${esc(row.stock_status||"—")}</b></div>${row.key_issue?`<div class="issue"><b>KEY ISSUE</b><p>${esc(row.key_issue)}</p></div>`:""}<div class="rating"><span>Movement Rating</span><b>${row.movement} / 10</b></div><div class="rating-bar"><i style="width:${row.movement*10}%;background:${color}"></i></div>${ratings?`<div class="product-ratings"><strong>PRODUCT RATINGS (${ratings.length})</strong>${ratings.slice(0,30).map(item=>`<div class="product-rating"><span>${esc(item.product)}</span><i class="score-pill ${esc(item.band)}">${item.movement}</i></div>`).join("")}</div>`:""}<div class="meta"><span>Report Date</span><b>${esc(row.report_date||"—")}</b><span>Submitter</span><b>${esc(row.submitter||"—")}</b></div><a class="navigate" href="${destination}" target="_blank" rel="noopener">Navigate</a>`;
  $("detailCard").querySelector(".close-detail").onclick=closeDetail;$("detailCard").classList.remove("hidden");
}
function closeDetail(){state.selected=null;$("detailCard").classList.add("hidden")}
function setFilters(open){$("filterPanel").classList.toggle("open",open);$("drawerBackdrop").classList.toggle("show",open)}
document.querySelectorAll(".tab").forEach(button=>button.onclick=()=>{document.querySelectorAll(".tab").forEach(item=>item.classList.toggle("active",item===button));$("filtersTab").classList.toggle("active",button.dataset.tab==="filters");$("layersTab").classList.toggle("active",button.dataset.tab==="layers")});
$("openFilters").onclick=()=>setFilters(true);$("closeFilters").onclick=()=>setFilters(false);$("drawerBackdrop").onclick=()=>setFilters(false);$("category").onchange=updateProducts;
$("applyBtn").onclick=()=>{setFilters(false);loadData({preserveOptions:true})};
$("resetBtn").onclick=()=>{["region","dealer","reportDate","province","district","commune","category","product","movement"].forEach(id=>$(id).value="");updateProducts();loadData({preserveOptions:true})};
$("refreshBtn").onclick=()=>loadData({preserveOptions:true,preserveView:true});
$("movementLayer").onchange=event=>event.target.checked?movementGroup.addTo(map):movementGroup.remove();$("labelsLayer").onchange=event=>event.target.checked?labels.addTo(map):labels.remove();
document.querySelectorAll('input[name="basemap"]').forEach(input=>input.onchange=()=>{if(!input.checked)return;if(input.value==="satellite"){map.removeLayer(street);satellite.addTo(map);satellite.bringToBack()}else{map.removeLayer(satellite);street.addTo(map);street.bringToBack()}});
map.on("click",()=>closeDetail());map.on("movestart zoomstart",()=>{if(isPhone)$("map").classList.add("map-moving")});map.on("moveend zoomend",()=>$("map").classList.remove("map-moving"));window.addEventListener("orientationchange",()=>setTimeout(()=>map.invalidateSize({animate:false}),150));
loadData();
