"use strict";
window.RadarMap = (() => {
  let loading, map, clusters, tileLayer, activePopup, previousKey = "", renderVersion = 0;
  const key = value => String(value || "").normalize("NFKC").toLocaleLowerCase("de").replace(/\s+/g," ").trim();
  let places = [];
  function setPlaces(data) {
    places = (Array.isArray(data.places) ? data.places : []).filter(p => typeof p.name === "string"
      && Number.isFinite(p.lat) && Number.isFinite(p.lon) && p.lat > 47 && p.lat < 49.5 && p.lon > 10 && p.lon < 13
      && Array.isArray(p.aliases));
  }
  function locate(event) {
    const name = key(event.location_name);
    if (!name) return null;
    return places.find(p => p.aliases.some(alias => key(alias) === name))
      || places.find(p => (p.prefixes || []).some(prefix => name.startsWith(key(prefix))))
      || places.find(p => (p.suffixes || []).some(suffix => name.endsWith(key(suffix)))) || null;
  }
  function asset(tag, url) {
    return new Promise((resolve,reject) => {
      const node = document.createElement(tag);
      if (tag === "script") node.src = url;
      else {node.rel = "stylesheet"; node.href = url;}
      node.onload = resolve;
      node.onerror = () => {node.remove(); reject(new Error("Kartenbestandteile konnten nicht geladen werden."));};
      document.head.append(node);
    });
  }
  function initialize() {
    if (!loading) loading = (async () => {
      await Promise.all([
        asset("link","./vendor/leaflet/leaflet.css"),
        asset("link","./vendor/leaflet.markercluster/MarkerCluster.css"),
        asset("link","./vendor/leaflet.markercluster/MarkerCluster.Default.css"),
        window.L ? Promise.resolve() : asset("script","./vendor/leaflet/leaflet.js")
      ]);
      if (!L.markerClusterGroup) await asset("script","./vendor/leaflet.markercluster/leaflet.markercluster.js");
      map = L.map("event-map", {scrollWheelZoom:false}).setView([48.137,11.576],11);
      map.on("popupopen", event => {activePopup = event.popup;});
      map.on("popupclose", () => {activePopup = null;});
      // Re-measure responsive content after rotation before keeping it inside the map.
      map.on("resize", () => {if (activePopup) activePopup.update();});
      tileLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
      }).addTo(map);
      tileLayer.on("tileerror", () => {
        document.querySelector("#map-tile-notice").hidden = false;
      });
      clusters = L.markerClusterGroup({maxClusterRadius:45, showCoverageOnHover:false, animate:false,
        iconCreateFunction:cluster => {
          const count = cluster.getAllChildMarkers().reduce((sum,m) => sum + m.options.eventCount,0);
          return L.divIcon({html:`<span>${count}</span>`,className:"radar-cluster",iconSize:[42,42]});
        }
      });
      map.addLayer(clusters);
    })().catch(error => {loading = null; throw error;});
    return loading;
  }
  async function show(events, popup, fitKey) {
    const version = ++renderVersion;
    const grouped = new Map(), missing = [];
    for (const event of events) {
      const place = locate(event);
      if (!place) {missing.push(event); continue;}
      if (!grouped.has(place.id)) grouped.set(place.id,{place,events:[]});
      grouped.get(place.id).events.push(event);
    }
    await initialize();
    if (version !== renderVersion) return;
    map.invalidateSize();
    clusters.clearLayers();
    for (const group of grouped.values()) {
      const {place,events:items} = group;
      const marker = L.marker([place.lat,place.lon], {
        eventCount:items.length, title:`${place.name}: ${items.length} Termine`, alt:place.name,
        icon:L.divIcon({html:`<span>${items.length}</span>`,className:"radar-marker",iconSize:[34,34],iconAnchor:[17,17]})
      });
      marker.bindPopup(() => popup(place,items), {maxWidth:300,minWidth:210,maxHeight:310,keepInView:true});
      clusters.addLayer(marker);
    }
    if (fitKey !== previousKey) {
      if (grouped.size) map.fitBounds(clusters.getBounds(),{padding:[30,30],maxZoom:14,animate:false});
      previousKey = fitKey;
    }
    const target = document.querySelector("#event-map");
    target.dataset.eventCount = events.length - missing.length;
    target.dataset.placeCount = grouped.size;
    target.setAttribute("aria-busy","false");
    return {mapped:events.length-missing.length, places:grouped.size, missing};
  }
  return {setPlaces,locate,show};
})();
