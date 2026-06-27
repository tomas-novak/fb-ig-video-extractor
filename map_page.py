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
    background: rgba(255,255,255,0.96); border-radius: 12px; padding: 10px 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 520px;
  }
  #panel h1 { font-size: 16px; margin: 0 0 8px; display: flex; align-items: center; gap: 8px; }
  #panel h1 .count { font-size: 12px; font-weight: normal; color: #666; }
  .filters { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;
    border: 2px solid #ccc; border-radius: 999px; padding: 4px 10px; font-size: 13px;
    background: #fff; transition: all .15s;
  }
  .chip .dot { width: 10px; height: 10px; border-radius: 50%; }
  .chip.off { opacity: .35; }
  .popup-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .popup-cat { display: inline-block; color: #fff; border-radius: 6px; padding: 1px 7px; font-size: 12px; margin-bottom: 6px; }
  .popup-tags { color: #666; font-size: 12px; margin-bottom: 6px; }
  .popup-summary { font-size: 13px; line-height: 1.4; margin-bottom: 8px; }
  .popup-link { font-size: 13px; }
  #status { font-size: 13px; color: #999; }
</style>
</head>
<body>
<div id="panel">
  <h1>🗺️ Výlety <span class="count" id="count"></span></h1>
  <div class="filters" id="filters"></div>
  <div id="status"></div>
</div>
<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const COLORS = {
  "koupání": "#2196f3", "turistika": "#4caf50", "jídlo": "#ff9800",
  "kultura": "#9c27b0", "příroda": "#009688", "sport": "#f44336",
  "zábava": "#e91e63", "jiné": "#607d8b"
};
function colorFor(cat){ return COLORS[cat] || COLORS["jiné"]; }
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c])); }

const map = L.map("map").setView([49.8, 15.5], 7);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap"
}).addTo(map);

const layers = {};   // kategorie -> L.layerGroup
const active = {};   // kategorie -> bool

function ensureLayer(cat){
  if(!layers[cat]){
    layers[cat] = L.layerGroup().addTo(map);
    active[cat] = true;
  }
  return layers[cat];
}

function renderFilters(){
  const box = document.getElementById("filters");
  box.innerHTML = "";
  Object.keys(layers).sort().forEach(cat => {
    const chip = document.createElement("span");
    chip.className = "chip" + (active[cat] ? "" : " off");
    chip.innerHTML = '<span class="dot" style="background:'+colorFor(cat)+'"></span>'+esc(cat);
    chip.onclick = () => {
      active[cat] = !active[cat];
      if(active[cat]) layers[cat].addTo(map); else map.removeLayer(layers[cat]);
      chip.classList.toggle("off");
    };
    box.appendChild(chip);
  });
}

fetch("/data").then(r => r.json()).then(places => {
  if(places.error){ document.getElementById("status").textContent = "Chyba: " + places.error; return; }
  document.getElementById("count").textContent = "(" + places.length + " míst)";
  const bounds = [];
  places.forEach(p => {
    const cat = p.category || "jiné";
    const grp = ensureLayer(cat);
    const m = L.circleMarker([p.lat, p.lng], {
      radius: 9, color: "#fff", weight: 2, fillColor: colorFor(cat), fillOpacity: 0.9
    });
    let html = '<div class="popup-title">'+esc(p.location_name)+'</div>';
    html += '<span class="popup-cat" style="background:'+colorFor(cat)+'">'+esc(cat)+'</span>';
    if(p.tags) html += '<div class="popup-tags">🏷️ '+esc(p.tags)+'</div>';
    if(p.summary) html += '<div class="popup-summary">'+esc(p.summary)+'</div>';
    if(p.url) html += '<div class="popup-link">▶️ <a href="'+esc(p.url)+'" target="_blank" rel="noopener">Otevřít video</a></div>';
    m.bindPopup(html);
    grp.addLayer(m);
    bounds.push([p.lat, p.lng]);
  });
  renderFilters();
  if(bounds.length) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
}).catch(e => {
  document.getElementById("status").textContent = "Nepodařilo se načíst data: " + e;
});
</script>
</body>
</html>
"""
