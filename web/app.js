"use strict";
(() => {
  const $ = (selector) => document.querySelector(selector);
  const labels = {festival:"Festival",street_festival:"Straßenfest",museum:"Museum & Kultur",exhibition:"Ausstellung",science:"Wissenschaft",technology:"Technik",family:"Familie",children:"Kinder",market:"Markt",flea_market:"Flohmarkt",culture:"Kultur",concert:"Musik & Konzert",theatre:"Theater",food:"Essen & Trinken",seasonal:"Saisonales",outdoor:"Draußen",city_event:"Stadtleben",public_event:"Öffentliches Programm",other:"Entdecken"};
  const titles = {today:"Heute auf dem Radar",tomorrow:"Das bringt der morgige Tag",weekend:"Dein Wochenende in München",upcoming:"Freu dich auf München",new:"Frisch im Radar",saved:"Meine Termine"};
  const zone = "Europe/Berlin";
  let events = [], metadata = null, view = "today", filter = "all", display = "list", calendarEvent = null;
  let mapRenderKey = "", mapGeneration = 0, placesLoaded = true;
  const personal = window.RadarPersonal;
  const fmt = (value, options) => new Intl.DateTimeFormat("de-DE", {timeZone:zone,...options}).format(new Date(value));
  const dayKey = (value) => {
    const parts = new Intl.DateTimeFormat("en-CA", {timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(value));
    const get = type => parts.find(p => p.type === type).value;
    return `${get("year")}-${get("month")}-${get("day")}`;
  };
  const shift = (day, n) => new Date(Date.parse(`${day}T12:00:00Z`) + n * 86400000).toISOString().slice(0,10);
  const daysBetween = (a,b) => Math.round((Date.parse(`${a}T12:00:00Z`) - Date.parse(`${b}T12:00:00Z`))/86400000);
  const weekend = today => {
    const weekday = new Date(`${today}T12:00:00Z`).getUTCDay();
    const saturday = shift(today, weekday === 0 ? -1 : 6 - weekday);
    return [saturday, shift(saturday,1)];
  };
  function onDay(event, day) {
    if (!event.start) return false;
    const start = dayKey(event.start);
    let end = event.end ? dayKey(event.end) : start;
    if (event.end && event.end !== event.start && fmt(event.end,{hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}) === "00:00:00") end = shift(end,-1);
    return start <= day && day <= end;
  }
  function belongs(event, target, today, now) {
    if (event.status !== "scheduled" || !event.start) return false;
    if (dayKey(event.end || event.start) < today || dayKey(event.start) > shift(today,metadata.selection.horizon_days)) return false;
    if (target === "today") return onDay(event,today);
    if (target === "tomorrow") return onDay(event,shift(today,1));
    if (target === "weekend") return weekend(today).some(day => onDay(event,day));
    if (target === "upcoming") return dayKey(event.start) > today && dayKey(event.start) <= shift(today,metadata.selection.horizon_days);
    const age = now - new Date(event.discovered_at);
    return age >= 0 && age <= metadata.selection.new_hours*3600000;
  }
  function selected(candidates) {
    const sources = new Map(), series = new Map(), result = [];
    for (const event of [...candidates].sort((a,b) => b.relevance_score-a.relevance_score || a.start.localeCompare(b.start) || a.id.localeCompare(b.id))) {
      const id = event.series_id || event.title.toLocaleLowerCase("de");
      if (event.relevance_score < metadata.selection.min_score || (sources.get(event.source_name)||0) >= metadata.selection.max_per_source || (series.get(id)||0) >= metadata.selection.max_per_series) continue;
      result.push(event); sources.set(event.source_name,(sources.get(event.source_name)||0)+1); series.set(id,(series.get(id)||0)+1);
      if (result.length >= metadata.selection.limit) break;
    }
    return result;
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function link(url, text, className="") {
    const node = element("a",className,text);
    try { const parsed = new URL(url); if (["https:","http:"].includes(parsed.protocol)) node.href = parsed.href; } catch { /* Invalid source links stay inert. */ }
    node.target = "_blank"; node.rel = "noopener noreferrer";
    return node;
  }
  function dateText(event, today) {
    if (!event.start) return "Termin noch offen";
    const start = dayKey(event.start), end = personal.lastDay(event);
    const time = value => fmt(value,{hour:"2-digit",minute:"2-digit"});
    if (start !== end) {
      const lastDate = fmt(`${end}T12:00:00Z`,{day:"numeric",month:"short"});
      if (start < today) return `Läuft bis ${lastDate} · Zeiten beim Veranstalter`;
      return `${fmt(event.start,{day:"numeric",month:"short"})} – ${lastDate}`;
    }
    const day = start === today ? "Heute" : start === shift(today,1) ? "Morgen" : fmt(event.start,{weekday:"short",day:"numeric",month:"short"});
    if (event.all_day) return `${day} · Zeiten beim Veranstalter`;
    return `${day} · ${time(event.start)}${event.end ? `–${time(event.end)}` : ""} Uhr`;
  }
  function card(event, index, today) {
    const featured = index === 0 && view !== "saved";
    const article = element("article",`event-card${featured ? " featured" : ""}`);
    const top = element("div","card-top");
    top.append(element("span","category",`${featured ? "IM FOKUS · " : ""}${labels[event.category] || "Entdecken"}`), element("span","card-index",String(index+1).padStart(2,"0")));
    const facts = element("div","event-facts");
    facts.append(element("span","fact-time",dateText(event,today)));
    if (event.location_name) facts.append(element("span","",event.location_name));
    facts.append(element("span","",event.is_free ? "Kostenlos" : event.price_text || "Preis beim Veranstalter"));
    article.append(top,element("h3","",event.title),facts);
    if (event.description) article.append(element("p","event-description",event.description));
    const why = element("div","why"), reasons = element("div","reasons");
    for (const reason of event.relevance_reasons.slice(0,4)) reasons.append(element("span","reason",reason));
    why.append(element("p","why-label","WARUM INTERESSANT"),reasons);
    const bottom = element("div","card-bottom"), sources = element("span","source-label");
    event.sources.forEach((source,i) => { if (i) sources.append(document.createTextNode(" · ")); sources.append(link(source.url,source.name)); });
    const more = link(event.source_url,"Mehr erfahren", "event-link"); more.append(element("span","","↗"));
    more.setAttribute("aria-label",`Mehr erfahren: ${event.title} (externe Quelle)`);
    bottom.append(sources,more); article.append(why,bottom);
    article.append(actions(event));
    if (event.stale) article.append(element("p","stale-label","Quelle derzeit nicht erreichbar · Termin bitte bestätigen"));
    if (view === "saved" && !events.some(e => e.id === event.id)) article.append(element("p","stale-label","Nicht im aktuellen Datenstand. Gespeicherter Termin – Angaben bitte beim Veranstalter prüfen."));
    return article;
  }
  function announce(message) {
    $("#personal-status").textContent = personal.issue() || message;
  }
  function updateSavedButtons() {
    $("#saved-count").textContent = personal.all().length;
    document.querySelectorAll("[data-save-id]").forEach(button => {
      const marked = personal.has(button.dataset.saveId);
      button.textContent = marked ? "✓ Gemerkt" : "+ Merken";
      button.setAttribute("aria-pressed",String(marked));
    });
  }
  function exportCalendar(event) {
    const start = dayKey(event.start), end = personal.lastDay(event);
    if (start !== end && (event.all_day || new Date(event.end) - new Date(event.start) > 86400000)) {
      calendarEvent = event;
      $("#calendar-event-title").textContent = event.title;
      const input = $("#calendar-day"), today = dayKey(new Date());
      input.min = start; input.max = end; input.value = today >= start && today <= end ? today : start;
      $("#calendar-dialog").showModal();
    } else {
      personal.download(event);
      announce("Kalenderdatei erstellt. Beim Öffnen in deinen Kalender übernehmen; Änderungen werden nicht automatisch aktualisiert.");
    }
  }
  function actions(event) {
    const container = element("div","event-actions");
    const save = element("button","action-button"); save.type = "button"; save.dataset.saveId = event.id;
    save.textContent = personal.has(event.id) ? "✓ Gemerkt" : "+ Merken";
    save.setAttribute("aria-pressed",String(personal.has(event.id)));
    save.setAttribute("aria-label",`Merken oder entfernen: ${event.title}`);
    save.addEventListener("click", () => {
      const marked = personal.toggle(event); updateSavedButtons();
      announce(marked ? "In deiner Merkliste gespeichert – nur in diesem Browser." : "Aus deiner Merkliste entfernt. Bereits importierte Kalendereinträge bleiben erhalten.");
      if (view === "saved" || $("#map-saved-only").checked) {mapRenderKey = ""; render();}
    });
    const calendar = element("button","action-button","In Kalender übernehmen"); calendar.type = "button";
    calendar.dataset.calendarId = event.id;
    calendar.setAttribute("aria-label",`In Kalender übernehmen: ${event.title}`);
    calendar.addEventListener("click", () => exportCalendar(event));
    container.append(save,calendar);
    const destination = RadarMap.directions(event);
    if (destination) {
      const route = link(destination.url,destination.approximate ? "Ort prüfen ↗" : "Anfahrt ↗","action-button");
      route.setAttribute("aria-label",`${destination.approximate ? "Ort prüfen" : "Anfahrt"} mit Google Maps: ${event.title}`);
      container.append(route);
      if (destination.approximate) container.append(element("span","route-note","Nur das Gelände ist bekannt. Treffpunkt oder Eingang bitte beim Veranstalter prüfen."));
    }
    return container;
  }
  function mapEvent(event) {
    const node = element("article","map-event");
    node.append(element("h4","",event.title),element("p","",dateText(event,dayKey(new Date()))));
    if (event.location_name) node.append(element("p","",event.location_name));
    node.append(actions(event),link(event.source_url,"Beim Veranstalter ansehen ↗"));
    return node;
  }
  function mapPopup(place,items) {
    const node = element("div","map-popup");
    node.append(element("h3","",place.name));
    if (place.approximate) node.append(element("p","","Gelände / ungefährer Bereich; genauen Treffpunkt beim Veranstalter prüfen."));
    items.sort((a,b) => a.start.localeCompare(b.start)).forEach(event => node.append(mapEvent(event)));
    return node;
  }
  async function renderMap(candidates) {
    const key = JSON.stringify([view,filter,$("#map-saved-only").checked,candidates.map(e => [e.id,personal.has(e.id)])]);
    if (key === mapRenderKey) return;
    mapRenderKey = key;
    const generation = ++mapGeneration;
    $("#event-map").setAttribute("aria-busy","true");
    $("#map-summary").textContent = "Veranstaltungsorte werden geladen …";
    const missing = candidates.filter(e => !RadarMap.locate(e));
    $("#map-missing").hidden = missing.length === 0;
    $("#map-missing-title").textContent = `${missing.length} ${missing.length === 1 ? "Termin ohne eindeutigen Kartenort" : "Termine ohne eindeutigen Kartenort"}`;
    $("#map-missing-events").replaceChildren(...missing.map(mapEvent));
    try {
      const result = await RadarMap.show(candidates,mapPopup,`${view}:${filter}:${$("#map-saved-only").checked}`);
      if (!result || generation !== mapGeneration) return;
      $("#map-summary").textContent = candidates.length
        ? `${result.mapped} von ${candidates.length} Terminen an ${result.places} Orten auf der Karte.${placesLoaded ? "" : " Ortsdaten konnten nicht geladen werden."}`
        : "Keine Termine für diese Auswahl. Ändere den Zeitraum oder die Filter.";
    } catch {
      if (generation !== mapGeneration) return;
      $("#event-map").setAttribute("aria-busy","false");
      const retry = element("button","action-button","Karte erneut laden"); retry.type = "button";
      retry.addEventListener("click", () => {mapRenderKey = ""; render();});
      $("#map-summary").replaceChildren(document.createTextNode("Karte konnte nicht geladen werden. Die Liste und deine Merkliste funktionieren weiterhin. "),retry);
    }
  }
  function render() {
    if (!metadata) return;
    const now = new Date(), today = dayKey(now);
    $("#today-date").textContent = `MÜNCHEN · ${fmt(now,{weekday:"long",day:"numeric",month:"long",year:"numeric"})}`;
    $("#selection-title").textContent = titles[view];
    const sat = weekend(today)[0];
    const dates = {today:fmt(now,{weekday:"long",day:"numeric",month:"long"}),tomorrow:fmt(`${shift(today,1)}T12:00:00Z`,{weekday:"long",day:"numeric",month:"long"}),weekend:`${fmt(`${sat}T12:00:00Z`,{day:"numeric",month:"short"})} – ${fmt(`${shift(sat,1)}T12:00:00Z`,{day:"numeric",month:"short"})}`,upcoming:`DIE NÄCHSTEN ${metadata.selection.horizon_days} TAGE`,new:`IN DEN LETZTEN ${metadata.selection.new_hours} STUNDEN ENTDECKT`,saved:"DEINE PERSÖNLICHE MERKLISTE"};
    $("#view-date").textContent = dates[view];
    const pool = view === "saved" ? personal.all() : events.filter(e => belongs(e,view,today,now));
    let candidates = pool.filter(e => (filter !== "free" || e.is_free === true) && (filter !== "family" || e.family_friendly === true));
    if (display === "map" && $("#map-saved-only").checked) candidates = candidates.filter(e => personal.has(e.id));
    const chosen = view === "saved" ? [...candidates].sort((a,b) => a.start.localeCompare(b.start)) : selected(candidates);
    const container = $("#events"); container.replaceChildren(); container.setAttribute("aria-busy","false");
    const count = display === "map" ? candidates.length : chosen.length;
    $("#selection-count").textContent = `${count} ${display === "list" && view !== "saved" ? count === 1 ? "Tipp" : "Tipps" : count === 1 ? "Termin" : "Termine"}`;
    container.hidden = display === "map";
    $("#map-panel").hidden = display !== "map";
    $("#personal-note").hidden = view !== "saved";
    $(".filter-note").textContent = display === "map" || view === "saved" ? "Alle passenden Termine" : "Nach Relevanz sortiert";
    if (display === "map") renderMap(candidates);
    else chosen.forEach((e,i) => container.append(card(e,i,today)));
    if (!chosen.length && display === "list") {
      const empty = element("div","empty-state",view === "saved" && filter === "all" ? "Noch nichts gemerkt. Tippe bei einer Veranstaltung auf „Merken“, um hier deine persönliche Auswahl zu sammeln." : filter === "all" ? "Für diesen Zeitraum ist gerade kein passender Tipp in unseren Quellen. Schau bei „Demnächst“ oder direkt in die Kalender." : "Für diesen Filter gibt es gerade keine passenden Tipps. Unbekannte Preise und Zielgruppen zählen hier nicht als Treffer.");
      if (filter !== "all") {const reset = element("button","","Alle Tipps anzeigen"); reset.type="button"; reset.addEventListener("click",() => setFilter("all")); empty.append(reset);}
      container.append(empty);
    }
    $("#selection-footnote").hidden = !chosen.length || display === "map" || view === "saved";
    updateSavedButtons();
    if (personal.issue()) announce("");
    const heads = $("#heads-up-events"); heads.replaceChildren();
    const previewSeries = new Set();
    const preview = events.filter(e => {
      if (!e.start || e.stale || e.status !== "scheduled" || e.tags.includes("recurring") || e.relevance_score < metadata.selection.min_score) return false;
      const days = daysBetween(dayKey(e.start),today);
      const series = e.series_id || e.title.toLocaleLowerCase("de");
      if (previewSeries.has(series) || !(e.tags.includes("major_event") ? metadata.heads_up_rules.major_days : metadata.heads_up_rules.other_days).includes(days)) return false;
      previewSeries.add(series);
      return true;
    }).slice(0,metadata.heads_up_rules.limit);
    for (const e of preview) {
      const days = daysBetween(dayKey(e.start),today), block = element("article","heads-up-item"), h = element("h3");
      h.append(link(e.source_url,e.title));
      block.append(element("span","days",days === 1 ? "Morgen" : `In ${days} Tagen`),h,element("p","",`${fmt(e.start,{day:"numeric",month:"long"})} · ${e.location_name || e.source_name}`)); heads.append(block);
    }
    if (!preview.length) heads.append(element("p","aside-copy","Gerade kein Termin an den Vormerkschwellen. Unter „Demnächst“ findest du weitere kommende Veranstaltungen."));
    const old = now - new Date(metadata.last_updated) > 24*3600000;
    const partial = metadata.sources.some(s => s.status !== "ok");
    const notice = $("#data-notice"); notice.hidden = !old && !partial;
    notice.textContent = old ? "Dieser Datenstand ist älter als 24 Stunden. Bitte bestätige die Termine direkt beim Veranstalter." : "Ein Teil der Quellen konnte nicht vollständig aktualisiert werden. Betroffene ältere Termine sind markiert.";
  }
  function setFilter(value) {
    filter = value;
    document.querySelectorAll("[data-filter]").forEach(button => {const active=button.dataset.filter===filter; button.classList.toggle("active",active); button.setAttribute("aria-pressed",String(active));});
    render();
  }
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click",() => {
    view=button.dataset.view;
    document.querySelectorAll("[data-view]").forEach(b => {const active=b===button;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
    render();
  }));
  document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click",() => setFilter(button.dataset.filter)));
  document.querySelectorAll("[data-display]").forEach(button => button.addEventListener("click",() => {
    display = button.dataset.display;
    document.querySelectorAll("[data-display]").forEach(b => {const active = b === button; b.classList.toggle("active",active); b.setAttribute("aria-pressed",String(active));});
    mapRenderKey = ""; render();
  }));
  $("#map-saved-only").addEventListener("change",render);
  $("#calendar-cancel").addEventListener("click",() => $("#calendar-dialog").close());
  $("#calendar-whole").addEventListener("click",() => {
    if (calendarEvent) personal.download(calendarEvent);
    $("#calendar-dialog").close(); announce("Kalenderdatei für den gesamten Zeitraum erstellt. Einmalige Kopie ohne automatische Aktualisierung.");
  });
  $("#calendar-form").addEventListener("submit",event => {
    event.preventDefault();
    if (!calendarEvent || !$("#calendar-form").reportValidity()) return;
    personal.download(calendarEvent,$("#calendar-day").value);
    $("#calendar-dialog").close(); announce("Kalenderdatei für deinen Besuchstag erstellt. Einmalige Kopie ohne automatische Aktualisierung.");
  });
  window.addEventListener("storage", event => {
    if (event.key === personal.storageKey || event.key === null) {personal.read(); mapRenderKey = ""; render();}
  });
  async function load() {
    try {
      const responses = await Promise.all([fetch("./data/events.json",{cache:"no-cache"}),fetch("./data/metadata.json",{cache:"no-cache"})]);
      if (responses.some(response => !response.ok)) throw new Error("Data unavailable");
      [events,metadata] = await Promise.all(responses.map(r => r.json()));
      if (!Array.isArray(events) || metadata.schema_version !== 1) throw new Error("Unsupported data format");
      try {
        const response = await fetch("./data/places.json");
        if (!response.ok) throw new Error("Places unavailable");
        RadarMap.setPlaces(await response.json()); placesLoaded = true;
      } catch {placesLoaded = false;}
      personal.refresh(events);
      const sources=$("#sources"); sources.replaceChildren();
      for (const source of metadata.sources) {
        const item=element("li"); item.append(link(source.url,source.name),element("span",`source-status${source.status === "ok" ? "" : " problem"}`,{ok:"Im Radar",partial:"Teilweise",error:"Nicht erreichbar"}[source.status] || "Unbekannt"));sources.append(item);
      }
      $("#updated").textContent=`Letzter Abruf: ${fmt(metadata.last_updated,{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})} Uhr · Berlin`;
      render();
    } catch {
      metadata=null;
      const container=$("#events");container.replaceChildren();container.setAttribute("aria-busy","false");
      const message=element("div","empty-state","Die Veranstaltungsdaten konnten nicht geladen werden. Bitte versuche es noch einmal.");
      const retry=element("button","","Erneut versuchen");retry.type="button";retry.addEventListener("click",load);message.append(retry);container.append(message);
      $("#updated").textContent="Datenstand nicht verfügbar";
      $("#heads-up-events").replaceChildren(element("p","aside-copy","Vorschau aktuell nicht verfügbar."));
    }
  }
  load();
  setInterval(render,60000);
  document.addEventListener("visibilitychange",() => {if (!document.hidden) render();});
})();
