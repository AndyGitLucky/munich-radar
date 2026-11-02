"use strict";
// Map is the interface. The existing app supplies filtering, ranking, cards and actions.
(() => {
  const $ = selector => document.querySelector(selector);
  const node = (tag, cls, text) => {
    const el = document.createElement(tag); if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text; return el;
  };
  const button = (text, cls, action) => {
    const el = node("button", cls, text); el.type = "button";
    if (action) el.addEventListener("click", action); return el;
  };
  const shell = $(".shell"), stage = $("#selection"), mapPanel = $("#map-panel");
  const masthead = $(".masthead"), nav = $(".view-nav"), topics = $("#topic-filters");
  const info = node("dialog", "prototype-info"); info.id = "prototype-info";
  info.setAttribute("aria-labelledby", "prototype-info-title");
  const infoHead = node("div", "sheet-head");
  const infoTitle = node("h2", "", "Dein Radar"); infoTitle.id = "prototype-info-title";
  infoHead.append(infoTitle, button("Schließen", "sheet-close", () => info.close())); info.append(infoHead);
  const infoBody = node("div", "sheet-body"); info.append(infoBody);
  const filters = node("dialog", "prototype-filters"); filters.id = "prototype-filters";
  filters.setAttribute("aria-labelledby", "prototype-filter-title");
  const filterHead = node("div", "sheet-head");
  const filterTitle = node("h2", "", "Auswahl eingrenzen"); filterTitle.id = "prototype-filter-title";
  filterHead.append(filterTitle, button("Fertig", "sheet-close", () => filters.close())); filters.append(filterHead);
  const filterBody = node("div", "sheet-body"); filters.append(filterBody);
  const details = node("dialog", "prototype-detail"); details.id = "prototype-detail";
  details.setAttribute("aria-labelledby", "prototype-detail-title");
  const detailHead = node("div", "sheet-head");
  const detailTitle = node("h2"); detailTitle.id = "prototype-detail-title";
  detailHead.append(detailTitle, button("Schließen", "sheet-close", () => details.close())); details.append(detailHead);
  const detailBody = node("div", "sheet-body"); details.append(detailBody);
  let focusBack = null;
  details.addEventListener("close", () => {
    if (focusBack?.isConnected) focusBack.focus({preventScroll:true});
    else $("#event-map").focus({preventScroll:true});
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && details.open && !$("#calendar-dialog").open && !info.open && !filters.open) details.close();
  });
  for (const dialog of [info, filters]) dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  });
  // Reuse original controls rather than approximating their behavior.
  infoBody.append($(".intro"), $(".section-heading"), $("#personal-note"), $("#topic-status"), $(".content-grid > aside"), $("footer"));
  filterBody.append($(".filter-row"), $(".map-saved-filter"));
  const occasionPanel = $("#occasion-panel"), occasions = $("#occasion-buttons");
  infoBody.prepend(occasionPanel);
  const dataNotice = $("#data-notice"); infoBody.prepend(dataNotice);
  const mapSummary = $("#map-summary"); infoBody.append(mapSummary);
  const mapNote = $(".map-note");
  mapNote.replaceChildren(document.createTextNode("Illustrationsprototyp · Lage vereinfacht. Die Kiesel zeigen Orte, keine bestätigten Eingänge. Ortsdaten: © OpenStreetMap-Mitwirkende. "));
  const credit = node("a", "", "Ortsdaten ansehen"); credit.href = "https://www.openstreetmap.org/copyright"; credit.target = "_blank"; credit.rel = "noopener noreferrer"; mapNote.append(credit);
  infoBody.append(mapNote, $("#map-missing"));
  const hiddenControls = node("div", "prototype-engine");
  hiddenControls.append($(".display-options"), $("#all-results"), $("#selection-footnote"));
  const originalLink = node("a", "prototype-original", "Bisherige Ansicht ↗"); originalLink.href = "/original/";
  infoBody.append(originalLink, node("p", "prototype-local-note", "Lokaler Designprototyp. Diese Browseradresse hat ihre eigene Merkliste; die veröffentlichte App bleibt unverändert."));
  const header = node("header", "prototype-header");
  masthead.append(nav);
  $(".brand").href = "/";
  $(".skip-link").href = "/#selection";
  $(".skip-link").addEventListener("click", event => {
    event.preventDefault(); $("#event-map").focus({preventScroll:true});
  });
  const infoButton = button("Info", "prototype-header-button", () => info.showModal());
  masthead.append(infoButton);
  const filterRow = node("div", "prototype-filterbar");
  filterRow.append(topics, occasions, button("Filter", "prototype-filter-button", () => filters.showModal()));
  const tally = node("span", "prototype-tally", "Termine werden geladen …"); tally.setAttribute("role", "status"); filterRow.append(tally);
  header.append(masthead, filterRow);
  const events = $("#events"), personalStatus = $("#personal-status");
  const labels = node("div", "prototype-labels"); labels.setAttribute("aria-label", "Empfehlungen auf der Karte");
  const wires = document.createElementNS("http://www.w3.org/2000/svg", "svg"); wires.classList.add("prototype-wires"); wires.setAttribute("aria-hidden", "true");
  const mapTools = node("div", "prototype-map-tools");
  const home = button("Ausschnitt", "prototype-map-button", () => resetView());
  const all = button("Alle Orte", "prototype-map-button", () => fitAll());
  mapTools.append(home, all);
  const missingButton = button("", "prototype-missing", () => openEvents(state.candidates.filter(e => !RadarMap.locate(e)), "Termine ohne Kartenort", missingButton));
  const status = node("div", "prototype-state", "Karte wird geladen …"); status.setAttribute("role", "status");
  const warning = button("Datenstand prüfen", "prototype-warning", () => info.showModal()); warning.hidden = true;
  const smallNote = node("span", "prototype-corner-note", "Entwurf · Lage vereinfacht");
  stage.replaceChildren(mapPanel, wires, labels, mapTools, missingButton, warning, smallNote, status, events, personalStatus);
  stage.className = "prototype-viewport";
  shell.replaceChildren(header, stage, hiddenControls, info, filters, details);
  document.body.classList.add("prototype-map-app");
  $("#event-map").setAttribute("aria-label", "Stilisierte Münchenkarte mit Terminen. Mit Pfeiltasten verschieben, mit Plus und Minus zoomen.");
  $("#event-map").tabIndex = 0;

  // ATLAS_PRESENTATION
  function openEvents(items, title, trigger) {
    if (!state || !items.length) return;
    focusBack = trigger; detailTitle.textContent=title;
    detailBody.replaceChildren(...items.map(event => state.createCard(event)));
    details.show(); details.scrollTop=0;
    details.querySelector(".sheet-close").focus({preventScroll:true});
  }
  function openGroup(group, trigger) {
    if (group.place) {
      const marker = markers.get(group.place.id);
      const anchor = L.latLng(position(group.place));
      if (!map.getBounds().contains(anchor)) map.panTo(anchor,{animate:false});
      if (marker && cluster.hasLayer(marker)) cluster.zoomToShowLayer(marker, () => {});
    }
    openEvents(group.events, group.place?.name || "Empfehlungen ohne Kartenpunkt", trigger);
  }
  function buildLabels() {
    labels.replaceChildren(); labelItems=[];
    if (!state) return;
    const source = state.view === "saved" ? state.candidates.slice(0,5) : state.recommendations;
    const groups = new Map();
    for (const event of source) {
      const place = RadarMap.locate(event), key = place?.id || "missing";
      if (!groups.has(key)) groups.set(key,{place,events:[]}); groups.get(key).events.push(event);
    }
    for (const group of [...groups.values()].sort((a,b)=>Number(Boolean(b.place))-Number(Boolean(a.place)))) {
      const el = button("", "prototype-label", () => openGroup(group,el));
      el.dataset.place=group.place?.id || "missing"; el.setAttribute("aria-haspopup","dialog");
      el.append(node("span", "prototype-label-dot", group.place ? "●" : "?"));
      const text=node("span","prototype-label-copy");
      text.append(node("strong","",!group.place && group.events.length>1 ? `${group.events.length} Empfehlungen ohne Kartenpunkt` : group.events[0].title));
      const card=state.createCard(group.events[0]);
      const time=card.querySelector(".fact-time")?.textContent || "";
      text.append(node("small","",group.place?.name || (group.events.length>1 ? "Termine ansehen →" : group.events[0].location_name || "Ort offen")));
      text.append(node("small","prototype-label-meta",group.events.length>1 ? `+ ${group.events.length-1} weiterer Termin` : time));
      if (!group.place) text.append(node("small","prototype-no-place","Ohne Kartenpunkt"));
      el.append(text); labels.append(el); labelItems.push({el,group});
    }
    layoutSoon();
  }
  function layoutSoon() {cancelAnimationFrame(frame); frame=requestAnimationFrame(layout);}
  function layout() {
    if (!map) return;
    wires.replaceChildren();
    const mobile=matchMedia("(max-width:700px)").matches, r=stage.getBoundingClientRect();
    wires.setAttribute("viewBox",`0 0 ${r.width} ${r.height}`);
    if (!mobile) {
      const occupied=[];
      for (const item of labelItems) {
        const p=item.group.place ? map.latLngToContainerPoint(position(item.group.place)) : {x:15,y:25+occupied.length*96};
        const w=item.el.offsetWidth,h=item.el.offsetHeight;
        let x=p.x+25; if(x+w>r.width-65) x=p.x-w-25;
        x=Math.max(12,Math.min(r.width-w-65,x));
        let y=Math.max(12,Math.min(r.height-h-55,p.y-h/2));
        for (const b of occupied) if(x<b.x+b.w+8 && x+w+8>b.x && y<b.y+b.h+8 && y+h+8>b.y) y=b.y+b.h+10;
        y=Math.min(r.height-h-55,y); item.el.style.left=`${x}px`; item.el.style.top=`${y}px`;
        occupied.push({x,y,w,h});
      }
    } else for (const {el} of labelItems) {el.style.removeProperty("left");el.style.removeProperty("top");}
    const tray=labels.getBoundingClientRect();
    for (const {el,group} of labelItems) {
      if (!group.place) continue;
      const box=el.getBoundingClientRect();
      if (mobile && (box.bottom<tray.top+4 || box.top>tray.bottom-4)) continue;
      const p=map.latLngToContainerPoint(position(group.place));
      const sx=box.right-r.left-5,sy=Math.max(tray.top,Math.min(tray.bottom,box.top+box.height/2))-r.top;
      const d=`M ${sx} ${sy} Q ${(sx+p.x)/2} ${sy} ${p.x} ${p.y}`;
      for(const cls of ["prototype-wire-halo","prototype-wire"]) {
        const line=document.createElementNS(wires.namespaceURI,"path"); line.setAttribute("d",d); line.setAttribute("class",cls); wires.append(line);
      }
    }
  }
  labels.addEventListener("scroll",layoutSoon,{passive:true});
  matchMedia("(max-width:700px)").addEventListener("change",() => {layout(); layoutSoon();});
  window.addEventListener("radar:selection",event => {
    state=event.detail; window.__isarSelection=state;
    if(details.open) details.close();
    const missing=state.candidates.filter(item => !RadarMap.locate(item));
    missingButton.textContent=`${missing.length} ohne Kartenort`; missingButton.hidden=!missing.length;
    tally.textContent=`${state.recommendations.length} Empfehlungen · ${state.candidates.length} gefunden`;
    status.hidden=state.candidates.length>0;
    status.textContent=state.candidates.length ? "" : state.view==="saved" ? "Noch keine gemerkten Termine für diese Auswahl." : "Keine passenden Termine. Ändere den Zeitraum oder die Filter.";
    buildLabels();
    queueMicrotask(() => {warning.hidden=dataNotice.hidden;});
  });
  RadarMap.show = async (items, popup, key) => {
    const version=++renderVersion;
    try {await initialize();} catch(error) {
      status.hidden=false; status.replaceChildren(node("p","", "Karte konnte nicht geladen werden."),button("Erneut versuchen","prototype-map-button",()=>$("[data-display=map]").click()));
      throw error;
    }
    if(version!==renderVersion) return null;
    cluster.clearLayers(); markers=new Map();
    const groups=new Map(), missing=[];
    for(const event of items) {
      const place=RadarMap.locate(event); if(!place) {missing.push(event);continue;}
      if(!groups.has(place.id)) groups.set(place.id,{place,events:[]}); groups.get(place.id).events.push(event);
    }
    const recommended=new Set((state?.recommendations || []).map(event=>RadarMap.locate(event)?.id));
    for(const group of groups.values()) {
      const marker=L.marker(position(group.place),{eventCount:group.events.length,title:`${group.place.name}: ${group.events.length} Termine`,alt:group.place.name,
        icon:L.divIcon({html:`<span>${group.events.length}</span>`,className:`isar-pebble${recommended.has(group.place.id)?" isar-recommended":""}`,iconSize:[44,44],iconAnchor:[22,22]})});
      marker.on("click",()=>openGroup(group,marker.getElement())); cluster.addLayer(marker); markers.set(group.place.id,marker);
    }
    if(key!==viewKey) {viewKey=key;labels.scrollTop=0;}
    const target=$("#event-map"); target.dataset.eventCount=items.length-missing.length; target.dataset.placeCount=groups.size;target.setAttribute("aria-busy","false");
    window.__isarMap=map;
    buildLabels();
    return {mapped:items.length-missing.length,places:groups.size,missing};
  };
  // Occasion selection intentionally resets the original app to list mode. Normalize only
  // its presentation back to the primary illustrated map after its original handler runs.
  document.addEventListener("click",event => {
    if(event.target.closest("[data-occasion-id]")) $("[data-display=map]").click();
  });
  new MutationObserver(() => {
    if(events.getAttribute("aria-busy")==="false" && events.querySelector(".empty-state")) status.hidden=true;
  }).observe(events,{childList:true,attributes:true,attributeFilter:["aria-busy"]});
  $("[data-display=map]").click();
})();
