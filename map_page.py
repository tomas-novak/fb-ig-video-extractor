"""Statická HTML stránka s Leaflet mapou. Data si tahá z /data."""

MAP_HTML = r"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Výlety – mapa</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: -apple-system, Segoe UI, Roboto, sans-serif; }
  #map { position: absolute; top: 0; bottom: 0; left: 0; right: 0; }
  #panel {
    position: absolute; z-index: 1000; top: 10px; left: 10px; right: 10px;
    background: rgba(255,255,255,0.96); border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 560px;
    overflow: hidden;
  }
  #panel-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px; padding: 10px 12px; cursor: pointer;
  }
  #panel-head .title { font-size: 15px; font-weight: 600; }
  #panel-head .count { font-size: 12px; font-weight: normal; color: #666; }
  #toggle {
    border: none; background: #f0f0f0; border-radius: 8px; padding: 6px 12px;
    font-size: 14px; cursor: pointer; white-space: nowrap;
  }
  #panel-body { display: none; padding: 0 12px 12px; max-height: 60vh; overflow-y: auto; }
  #panel-body.open { display: block; }
  .group-label { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #888; margin: 8px 0 4px; }
  .group-head { display: flex; align-items: center; justify-content: space-between; }
  .mini { border: 1px solid #ccc; background: #fff; border-radius: 6px; padding: 2px 8px;
          font-size: 11px; cursor: pointer; margin-left: 4px; color: #333; }
  .mini:active { background: #eee; }
  .filters { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;
    border: 2px solid #ccc; border-radius: 999px; padding: 4px 10px; font-size: 13px;
    background: #fff; transition: all .15s;
  }
  .chip .dot { width: 10px; height: 10px; border-radius: 50%; }
  .chip.off { opacity: .35; }
  .chip.tag.on { border-color: #333; background: #333; color: #fff; }
  .popup-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .popup-cat { display: inline-block; color: #fff; border-radius: 6px; padding: 1px 7px; font-size: 12px; margin-bottom: 6px; }
  .popup-tags { color: #666; font-size: 12px; margin-bottom: 6px; }
  .popup-summary { font-size: 13px; line-height: 1.4; margin-bottom: 8px; }
  .popup-link { font-size: 13px; }
  #status { font-size: 13px; color: #999; padding: 0 12px 10px; }
</style>
</head>
<body>
<div id="panel">
  <div id="panel-head">
    <span class="title">🗺️ Výlety <span class="count" id="count"></span></span>
    <button id="toggle">☰ Filtry</button>
  </div>
  <div id="panel-body">
    <div class="group-label">Kategorie</div>
    <div class="filters" id="cat-filters"></div>
    <div class="group-label group-head">
      <span>Tagy</span>
      <span>
        <button class="mini" id="tags-all">vše</button>
        <button class="mini" id="tags-none">nic</button>
      </span>
    </div>
    <div class="filters" id="tag-filters"></div>
  </div>
  <div id="status"></div>
</div>
<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const COLORS = {
  "koupání": "#2196f3", "turistika": "#4caf50", "jídlo": "#ff9800",
  "kultura": "#9c27b0", "příroda": "#009688", "sport": "#f44336",
  "zábava": "#e91e63", "hotel": "#795548", "jiné": "#607d8b"
};
function colorFor(cat){ return COLORS[cat] || COLORS["jiné"]; }
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c])); }
function parseTags(s){ return (s||"").split(",").map(t => t.trim()).filter(Boolean); }

// Sbalovací panel filtrů (na mobilu jinak zakrývá mapu)
const body = document.getElementById("panel-body");
const toggleBtn = document.getElementById("toggle");
function setOpen(open){
  body.classList.toggle("open", open);
  toggleBtn.textContent = open ? "✕ Zavřít" : "☰ Filtry";
}
toggleBtn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!body.classList.contains("open")); });

const map = L.map("map").setView([49.8, 15.5], 7);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap"
}).addTo(map);
// Klik do mapy zavře panel filtrů
map.on("click", () => setOpen(false));

const markers = [];      // {marker, category, tags[]}
const activeCat = {};    // kategorie -> bool (default true)
const activeTag = {};    // tag -> bool (default true)

function placeVisible(item){
  if(!activeCat[item.category]) return false;
  if(item.tags.length === 0) return true;
  return item.tags.some(t => activeTag[t]);
}

function applyFilters(){
  let shown = 0;
  markers.forEach(item => {
    const vis = placeVisible(item);
    if(vis){ if(!map.hasLayer(item.marker)) item.marker.addTo(map); shown++; }
    else   { if(map.hasLayer(item.marker)) map.removeLayer(item.marker); }
  });
  document.getElementById("count").textContent = "(" + shown + " / " + markers.length + " míst)";
}

function buildCatFilters(){
  const box = document.getElementById("cat-filters");
  box.innerHTML = "";
  Object.keys(activeCat).sort().forEach(cat => {
    const chip = document.createElement("span");
    chip.className = "chip" + (activeCat[cat] ? "" : " off");
    chip.innerHTML = '<span class="dot" style="background:'+colorFor(cat)+'"></span>'+esc(cat);
    chip.onclick = () => { activeCat[cat] = !activeCat[cat]; chip.classList.toggle("off"); applyFilters(); };
    box.appendChild(chip);
  });
}

function buildTagFilters(){
  const box = document.getElementById("tag-filters");
  box.innerHTML = "";
  Object.keys(activeTag).sort((a,b)=>a.localeCompare(b,'cs')).forEach(tag => {
    const chip = document.createElement("span");
    chip.className = "chip tag" + (activeTag[tag] ? " on" : " off");
    chip.textContent = "#" + tag;
    chip.onclick = () => {
      activeTag[tag] = !activeTag[tag];
      chip.classList.toggle("on", activeTag[tag]);
      chip.classList.toggle("off", !activeTag[tag]);
      applyFilters();
    };
    box.appendChild(chip);
  });
}

fetch("/data").then(r => r.json()).then(places => {
  if(places.error){ document.getElementById("status").textContent = "Chyba: " + places.error; return; }
  const bounds = [];

  // Seskupení podle group_id (sloučená místa = jeden pin s více videi)
  const groups = {};
  places.forEach(p => {
    const key = p.group_id || ("solo-" + p.row);
    (groups[key] = groups[key] || []).push(p);
  });

  Object.values(groups).forEach(group => {
    const rep = group[0];  // reprezentant skupiny (první záznam)
    const cat = rep.category || "jiné";
    // tagy = sjednocení tagů všech videí ve skupině
    const tagSet = new Set();
    group.forEach(p => parseTags(p.tags).forEach(t => tagSet.add(t)));
    const tags = [...tagSet];
    activeCat[cat] = true;
    tags.forEach(t => activeTag[t] = true);

    const m = L.circleMarker([rep.lat, rep.lng], {
      radius: 9, color: "#fff", weight: 2, fillColor: colorFor(cat), fillOpacity: 0.9
    });
    let html = '<div class="popup-title">'+esc(rep.location_name)+'</div>';
    html += '<span class="popup-cat" style="background:'+colorFor(cat)+'">'+esc(cat)+'</span>';
    if(tags.length) html += '<div class="popup-tags">🏷️ '+esc(tags.join(", "))+'</div>';
    if(rep.summary) html += '<div class="popup-summary">'+esc(rep.summary)+'</div>';
    group.forEach((p, i) => {
      if(p.url){
        const label = group.length > 1 ? ("Video " + (i+1) + " (" + esc(p.date||"") + ")") : "Otevřít video";
        html += '<div class="popup-link">▶️ <a href="'+esc(p.url)+'" target="_blank" rel="noopener">'+label+'</a></div>';
      }
    });
    m.bindPopup(html);
    m.addTo(map);
    markers.push({ marker: m, category: cat, tags: tags });
    bounds.push([rep.lat, rep.lng]);
  });
  buildCatFilters();
  buildTagFilters();
  applyFilters();

  // Tlačítka vše/nic pro tagy – snadný výběr jednoho tagu (dej "nic", pak klikni jeden)
  function setAllTags(val){
    Object.keys(activeTag).forEach(t => activeTag[t] = val);
    buildTagFilters();
    applyFilters();
  }
  document.getElementById("tags-all").onclick = () => setAllTags(true);
  document.getElementById("tags-none").onclick = () => setAllTags(false);
  if(bounds.length) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
}).catch(e => {
  document.getElementById("status").textContent = "Nepodařilo se načíst data: " + e;
});
</script>
</body>
</html>
"""
