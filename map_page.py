"""HTML page with a Leaflet map. It pulls its data from /data.

The template is static; the language (BOT_LANGUAGE) and categories (CATEGORIES)
are substituted into it at render time by render_map() – the __MAP_*__ tokens.
"""
import json

from i18n import CATEGORIES, LANG


def render_map() -> str:
    """Substitute the language and categories from the configuration into the map HTML template."""
    return (MAP_HTML
            .replace("__MAP_LANG_ATTR__", LANG)
            .replace("__MAP_LANG__", json.dumps(LANG))
            .replace("__MAP_CATEGORIES__", json.dumps(CATEGORIES, ensure_ascii=False)))


MAP_HTML = r"""<!DOCTYPE html>
<html lang="__MAP_LANG_ATTR__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="referrer" content="no-referrer">
<title></title>
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
  .chip.visited-toggle.on { border-color: #4caf50; background: #4caf50; color: #fff; }
  .popup-thumb { width: 100%; max-height: 130px; object-fit: cover; border-radius: 8px; margin-bottom: 8px; display: block; }
  .popup-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .popup-cat { display: inline-block; color: #fff; border-radius: 6px; padding: 1px 7px; font-size: 12px; margin-bottom: 6px; }
  .popup-tags { color: #666; font-size: 12px; margin-bottom: 6px; }
  .popup-summary { font-size: 13px; line-height: 1.4; margin-bottom: 8px; }
  .popup-link { font-size: 13px; }
  .visit-btn {
    display: block; width: 100%; margin-top: 8px; padding: 6px 10px;
    border: 1px solid #4caf50; border-radius: 8px; background: #fff; color: #2e7d32;
    font-size: 13px; cursor: pointer;
  }
  .visit-btn.undo { border-color: #999; color: #555; }
  .visit-btn:disabled { opacity: .5; }
  .del-btn {
    display: block; width: 100%; margin-top: 6px; padding: 6px 10px;
    border: 1px solid #e57373; border-radius: 8px; background: #fff; color: #c62828;
    font-size: 13px; cursor: pointer;
  }
  .del-btn.armed { background: #c62828; border-color: #c62828; color: #fff; font-weight: 600; }
  .del-btn:disabled { opacity: .5; }
  #status { font-size: 13px; color: #999; padding: 0 12px 10px; }
</style>
</head>
<body>
<div id="panel">
  <div id="panel-head">
    <span class="title"><span id="panel-title"></span> <span class="count" id="count"></span></span>
    <button id="toggle"></button>
  </div>
  <div id="panel-body">
    <div class="group-label" id="label-view"></div>
    <div class="filters">
      <span class="chip visited-toggle" id="visited-toggle"></span>
    </div>
    <div class="group-label" id="label-categories"></div>
    <div class="filters" id="cat-filters"></div>
    <div class="group-label group-head">
      <span id="label-tags"></span>
      <span>
        <button class="mini" id="tags-all"></button>
        <button class="mini" id="tags-none"></button>
      </span>
    </div>
    <div class="filters" id="tag-filters"></div>
    <div class="group-label" id="label-export"></div>
    <div class="filters" id="export-links"></div>
  </div>
  <div id="status"></div>
</div>
<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
// The server substitutes the language and categories from the config (BOT_LANGUAGE, CATEGORIES)
const LANG = __MAP_LANG__;
const CATEGORIES = __MAP_CATEGORIES__;
const FALLBACK_CATEGORY = CATEGORIES[CATEGORIES.length - 1];

// UI texts – LANG picks the language
const TEXTS = {
  cs: {
    title: "Výlety – mapa", panelTitle: "🗺️ Výlety",
    filters: "☰ Filtry", close: "✕ Zavřít",
    view: "Zobrazení", categories: "Kategorie", tags: "Tagy", exportLabel: "Export",
    all: "vše", none: "nic", visitedOnly: "✓ jen navštívené",
    count: (shown, total) => "(" + shown + " / " + total + " míst)",
    openVideo: "Otevřít video", videoN: (n, date) => "Video " + n + " (" + date + ")",
    openPhoto: "Otevřít fotku", photoN: (n, date) => "Fotka " + n + " (" + date + ")",
    openMaps: "Otevřít v Google Maps",
    approx: "⚠️ přibližná poloha (odhad AI)",
    visit: "✅ Už jsme navštívili", unvisit: "↩️ Vrátit mezi nenavštívené",
    del: "🗑️ Smazat místo", delConfirm: "‼️ Opravdu úplně smazat? Klikni znovu",
    badToken: "Neplatný token – otevři mapu přes odkaz s ?token=...",
    badTokenLoad: "Neplatný nebo chybějící token – otevři mapu přes odkaz s ?token=...",
    deleteFailed: "Smazání se nepovedlo: ", saveFailed: "Uložení se nepovedlo: ",
    connError: "Chyba spojení: ", dataError: "Chyba: ", loadFailed: "Nepodařilo se načíst data: "
  },
  en: {
    title: "Trips – map", panelTitle: "🗺️ Trips",
    filters: "☰ Filters", close: "✕ Close",
    view: "View", categories: "Categories", tags: "Tags", exportLabel: "Export",
    all: "all", none: "none", visitedOnly: "✓ visited only",
    count: (shown, total) => "(" + shown + " / " + total + " places)",
    openVideo: "Open video", videoN: (n, date) => "Video " + n + " (" + date + ")",
    openPhoto: "Open photo", photoN: (n, date) => "Photo " + n + " (" + date + ")",
    openMaps: "Open in Google Maps",
    approx: "⚠️ approximate location (AI estimate)",
    visit: "✅ Mark as visited", unvisit: "↩️ Mark as not visited",
    del: "🗑️ Delete place", delConfirm: "‼️ Really delete? Click again",
    badToken: "Invalid token – open the map via a link with ?token=...",
    badTokenLoad: "Invalid or missing token – open the map via a link with ?token=...",
    deleteFailed: "Delete failed: ", saveFailed: "Save failed: ",
    connError: "Connection error: ", dataError: "Error: ", loadFailed: "Failed to load data: "
  }
};
const T = TEXTS[LANG] || TEXTS.cs;

// Static page texts
document.title = T.title;
document.getElementById("panel-title").textContent = T.panelTitle;
document.getElementById("label-view").textContent = T.view;
document.getElementById("label-categories").textContent = T.categories;
document.getElementById("label-tags").textContent = T.tags;
document.getElementById("label-export").textContent = T.exportLabel;
document.getElementById("tags-all").textContent = T.all;
document.getElementById("tags-none").textContent = T.none;
document.getElementById("visited-toggle").textContent = T.visitedOnly;

// The token from the map URL (/map?token=...) is passed to every data request
const TOKEN = new URLSearchParams(location.search).get("token") || "";
function withToken(path){ return TOKEN ? path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN) : path; }

// Colors are assigned to categories by their order in the configuration, so the
// default Czech set keeps the same colors as before. An unknown category (older
// data after a CATEGORIES change) gets grey.
const PALETTE = ["#2196f3", "#4caf50", "#ff9800", "#9c27b0", "#009688",
                 "#f44336", "#e91e63", "#795548", "#607d8b"];
const GREY = "#607d8b";
const COLORS = {};
CATEGORIES.forEach((cat, i) => { COLORS[cat] = PALETTE[i % PALETTE.length]; });
function colorFor(cat){ return COLORS[cat] || GREY; }
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c])); }
function parseTags(s){ return (s||"").split(",").map(t => t.trim()).filter(Boolean); }

// Collapsible filter panel (on mobile it would otherwise cover the map)
const body = document.getElementById("panel-body");
const toggleBtn = document.getElementById("toggle");
function setOpen(open){
  body.classList.toggle("open", open);
  toggleBtn.textContent = open ? T.close : T.filters;
}
setOpen(false);
toggleBtn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!body.classList.contains("open")); });

const map = L.map("map").setView([49.8, 15.5], 7);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap"
}).addTo(map);
map.on("click", () => setOpen(false));

let CAN_EDIT = true;     // false = read-only shared view (the server hides mutations)
const items = {};        // key -> {marker, category, tags[], visited, group[]}
const activeCat = {};    // category -> bool
const activeTag = {};    // tag -> bool
let visitedMode = false; // false = unvisited only, true = visited ONLY

function placeVisible(item){
  if(visitedMode !== item.visited) return false;
  if(!activeCat[item.category]) return false;
  if(item.tags.length === 0) return true;
  return item.tags.some(t => activeTag[t]);
}

function markerStyle(item){
  // visited places are grey so they stand out at a glance
  return { fillColor: item.visited ? "#9e9e9e" : colorFor(item.category) };
}

function applyFilters(){
  let shown = 0, total = 0;
  Object.values(items).forEach(item => {
    total++;
    const vis = placeVisible(item);
    if(vis){ if(!map.hasLayer(item.marker)) item.marker.addTo(map); shown++; }
    else   { if(map.hasLayer(item.marker)) map.removeLayer(item.marker); }
  });
  document.getElementById("count").textContent = T.count(shown, total);
}

function buildPopup(key){
  const item = items[key];
  const group = item.group;
  const rep = group[0];
  const cat = item.category;
  // Missing thumbnails (older rows, or the fetch/cache failed) just don't
  // show an image - the onerror handler removes the broken <img> itself.
  let html = '<img class="popup-thumb" src="'+withToken("/thumb/"+rep.row+".jpg")+'" onerror="this.remove()">';
  html += '<div class="popup-title">'+esc(rep.location_name)+'</div>';
  html += '<span class="popup-cat" style="background:'+colorFor(cat)+'">'+esc(cat)+'</span>';
  if(item.tags.length) html += '<div class="popup-tags">🏷️ '+esc(item.tags.join(", "))+'</div>';
  if(rep.summary) html += '<div class="popup-summary">'+esc(rep.summary)+'</div>';
  group.forEach((p, i) => {
    // "poi" entries (imported from a My Maps pin, no source video/photo) have
    // no meaningful link to open here - the 🧭 Google Maps link below covers it.
    if(p.url && p.media_type !== "poi"){
      const isPhoto = p.media_type === "photo";
      const icon = isPhoto ? "🖼️" : "▶️";
      const label = group.length > 1
        ? (isPhoto ? T.photoN(i+1, esc(p.date||"")) : T.videoN(i+1, esc(p.date||"")))
        : (isPhoto ? T.openPhoto : T.openVideo);
      html += '<div class="popup-link">'+icon+' <a href="'+esc(p.url)+'" target="_blank" rel="noopener">'+label+'</a></div>';
    }
  });
  const mapsUrl = rep.maps_url || ("https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(rep.location_name));
  html += '<div class="popup-link">🧭 <a href="'+esc(mapsUrl)+'" target="_blank" rel="noopener">'+T.openMaps+'</a></div>';
  if(rep.geo_source === "gemini"){
    html += '<div class="popup-tags">'+T.approx+'</div>';
  }
  if(CAN_EDIT){
    if(item.visited){
      html += '<button class="visit-btn undo" onclick="setVisited(\''+key+'\', false, this)">'+T.unvisit+'</button>';
    } else {
      html += '<button class="visit-btn" onclick="setVisited(\''+key+'\', true, this)">'+T.visit+'</button>';
    }
    html += '<button class="del-btn" onclick="deletePlace(\''+key+'\', this)">'+T.del+'</button>';
  }
  return html;
}

// Two-phase deletion: the 1st click arms it (red confirmation), the 2nd deletes.
// Without a confirmation within 5 s the button disarms itself again.
window.deletePlace = function(key, btn){
  const item = items[key];
  if(!item) return;
  if(!btn.dataset.armed){
    btn.dataset.armed = "1";
    btn.classList.add("armed");
    btn.textContent = T.delConfirm;
    setTimeout(() => {
      if(btn.dataset.armed){
        delete btn.dataset.armed;
        btn.classList.remove("armed");
        btn.textContent = T.del;
      }
    }, 5000);
    return;
  }
  btn.disabled = true;
  const rows = item.group.map(p => p.row);
  fetch(withToken("/delete"), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({rows: rows}),
  }).then(r => {
    if(r.status === 403) throw new Error(T.badToken);
    return r.json();
  }).then(res => {
    if(res.ok){
      // Deletion shifted the row numbers → reload the map with fresh data
      location.reload();
    } else {
      alert(T.deleteFailed + (res.error || "?"));
      btn.disabled = false;
    }
  }).catch(e => { alert(T.connError + e); btn.disabled = false; });
};

window.setVisited = function(key, flag, btn){
  const item = items[key];
  if(!item) return;
  btn.disabled = true;
  const rows = item.group.map(p => p.row);
  fetch(withToken("/visited"), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({rows: rows, visited: flag}),
  }).then(r => {
    if(r.status === 403) throw new Error(T.badToken);
    return r.json();
  }).then(res => {
    if(res.ok){
      item.visited = flag;
      item.marker.setStyle(markerStyle(item));
      item.marker.setPopupContent(buildPopup(key));
      item.marker.closePopup();
      applyFilters();
    } else {
      alert(T.saveFailed + (res.error || "?"));
      btn.disabled = false;
    }
  }).catch(e => { alert(T.connError + e); btn.disabled = false; });
};

function buildCatFilters(){
  const box = document.getElementById("cat-filters");
  box.innerHTML = "";
  // Chip order follows the configuration; categories outside it (older data) go last
  const order = cat => { const i = CATEGORIES.indexOf(cat); return i === -1 ? CATEGORIES.length : i; };
  Object.keys(activeCat).sort((a,b) => order(a) - order(b) || a.localeCompare(b, LANG)).forEach(cat => {
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
  Object.keys(activeTag).sort((a,b)=>a.localeCompare(b,LANG)).forEach(tag => {
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

// Export links (GeoJSON for web maps, GPX/KML for Mapy.cz, Organic Maps...)
const expBox = document.getElementById("export-links");
["geojson", "gpx", "kml"].forEach(fmt => {
  const a = document.createElement("a");
  a.className = "chip";
  a.textContent = "⬇ " + fmt.toUpperCase();
  a.href = withToken("/export?format=" + fmt);
  expBox.appendChild(a);
});

// Toggle for showing visited places
const visitedChip = document.getElementById("visited-toggle");
visitedChip.classList.add("off");
visitedChip.onclick = () => {
  visitedMode = !visitedMode;
  visitedChip.classList.toggle("on", visitedMode);
  visitedChip.classList.toggle("off", !visitedMode);
  applyFilters();
};

fetch(withToken("/data")).then(r => {
  if(r.status === 403) throw new Error(T.badTokenLoad);
  CAN_EDIT = r.headers.get("X-Can-Edit") !== "0";
  return r.json();
}).then(places => {
  if(places.error){ document.getElementById("status").textContent = T.dataError + places.error; return; }
  const bounds = [];

  // Grouping by group_id (merged places = one pin with multiple videos)
  const groups = {};
  places.forEach(p => {
    const key = p.group_id || ("solo-" + p.row);
    (groups[key] = groups[key] || []).push(p);
  });

  Object.entries(groups).forEach(([key, group]) => {
    const rep = group[0];
    const cat = rep.category || FALLBACK_CATEGORY;
    const tagSet = new Set();
    group.forEach(p => parseTags(p.tags).forEach(t => tagSet.add(t)));
    const tags = [...tagSet];
    const visited = group.some(p => p.visited);
    activeCat[cat] = true;
    tags.forEach(t => activeTag[t] = true);

    const m = L.circleMarker([rep.lat, rep.lng], {
      radius: 9, color: "#fff", weight: 2,
      fillColor: visited ? "#9e9e9e" : colorFor(cat), fillOpacity: 0.9
    });
    items[key] = { marker: m, category: cat, tags: tags, visited: visited, group: group };
    m.bindPopup(buildPopup(key));
    bounds.push([rep.lat, rep.lng]);
  });

  buildCatFilters();
  buildTagFilters();
  applyFilters();

  function setAllTags(val){
    Object.keys(activeTag).forEach(t => activeTag[t] = val);
    buildTagFilters();
    applyFilters();
  }
  document.getElementById("tags-all").onclick = () => setAllTags(true);
  document.getElementById("tags-none").onclick = () => setAllTags(false);

  if(bounds.length) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
}).catch(e => {
  document.getElementById("status").textContent = T.loadFailed + e;
});
</script>
</body>
</html>
"""
