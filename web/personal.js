"use strict";
// Device-local bookmarks and standards-compliant, one-time iCalendar exports.
window.RadarPersonal = (() => {
  const storageKey = "munich-radar.saved.v1";
  let saved = new Map(), storageIssue = "";
  function valid(event) {
    return event && typeof event.id === "string" && /^[a-f0-9]{20}$/.test(event.id)
      && typeof event.title === "string" && Number.isFinite(Date.parse(event.start))
      && (!event.end || Number.isFinite(Date.parse(event.end)))
      && Array.isArray(event.sources) && event.sources.every(s => s && typeof s.name === "string" && typeof s.url === "string")
      && Array.isArray(event.tags) && Array.isArray(event.relevance_reasons);
  }
  function read() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) { saved = new Map(); storageIssue = ""; return; }
      const data = JSON.parse(raw);
      if (data.version !== 1 || !Array.isArray(data.events) || !data.events.every(valid)) throw new Error("Invalid bookmarks");
      saved = new Map(data.events.map(event => [event.id, event]));
      storageIssue = "";
    } catch {
      storageIssue = "Die gespeicherte Merkliste ist nicht lesbar. Neue Markierungen gelten vorerst nur in dieser Sitzung.";
    }
  }
  function write() {
    if (storageIssue) return false;
    try {
      localStorage.setItem(storageKey, JSON.stringify({version:1, events:[...saved.values()]}));
      return true;
    } catch {
      storageIssue = "Dein Browser konnte die Merkliste nicht speichern. Neue Änderungen gelten nur in dieser Sitzung.";
      return false;
    }
  }
  read();
  function toggle(event) {
    if (saved.has(event.id)) saved.delete(event.id);
    else if (valid(event)) saved.set(event.id, structuredClone(event));
    write();
    return saved.has(event.id);
  }
  function refresh(events) {
    let changed = false;
    for (const event of events) {
      if (saved.has(event.id) && JSON.stringify(saved.get(event.id)) !== JSON.stringify(event)) {
        saved.set(event.id, structuredClone(event)); changed = true;
      }
    }
    if (changed) write();
  }
  const zone = "Europe/Berlin";
  function day(value) {
    const parts = new Intl.DateTimeFormat("en-CA", {timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(value));
    return ["year","month","day"].map(key => parts.find(p => p.type === key).value).join("-");
  }
  const nextDay = value => new Date(Date.parse(value+"T12:00:00Z")+86400000).toISOString().slice(0,10);
  function lastDay(event) {
    const end = day(event.end || event.start);
    if (!event.end || event.end === event.start) return end;
    const time = new Intl.DateTimeFormat("en-GB", {timeZone:zone,hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).format(new Date(event.end));
    return time === "00:00:00" ? new Date(Date.parse(end+"T12:00:00Z")-86400000).toISOString().slice(0,10) : end;
  }
  const stamp = value => new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const escape = value => String(value || "").replace(/\\/g,"\\\\").replace(/\r\n|\r|\n/g,"\\n").replace(/;/g,"\\;").replace(/,/g,"\\,");
  function safeUrl(value) {
    try { const url = new URL(value); return ["https:","http:"].includes(url.protocol) && !url.username && !url.password ? url.href : ""; }
    catch { return ""; }
  }
  function fold(line) {
    // RFC 5545: 75 octets, without splitting a UTF-8 character; continuation includes a space.
    const encoder = new TextEncoder();
    let result = "", length = 0;
    for (const char of line) {
      const size = encoder.encode(char).length;
      if (length + size > 75) { result += "\r\n "; length = 1; }
      result += char; length += size;
    }
    return result;
  }
  function calendar(event, visitDay = null, now = new Date()) {
    if (!valid(event)) throw new Error("Termin ohne gültiges Datum");
    const start = day(event.start), end = lastDay(event);
    if (visitDay && (!/^\d{4}-\d{2}-\d{2}$/.test(visitDay) || visitDay < start || visitDay > end
        || new Date(visitDay+"T12:00:00Z").toISOString().slice(0,10) !== visitDay)) throw new Error("Besuchstag liegt außerhalb des Termins");
    const lines = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Munich Radar//Termine//DE","CALSCALE:GREGORIAN",
      "BEGIN:VEVENT",`UID:${event.id}${visitDay ? "-"+visitDay : ""}@munich-radar.andygitlucky.github.io`, `DTSTAMP:${stamp(now)}`];
    if (visitDay || event.all_day) {
      lines.push(`DTSTART;VALUE=DATE:${(visitDay || start).replaceAll("-","")}`);
      lines.push(`DTEND;VALUE=DATE:${nextDay(visitDay || end).replaceAll("-","")}`);
    } else {
      lines.push(`DTSTART:${stamp(event.start)}`);
      if (event.end) lines.push(`DTEND:${stamp(event.end)}`);
    }
    const url = safeUrl(event.source_url);
    const description = [event.description,
      visitDay ? `Besuchstag für eine mehrtägige Veranstaltung (${start} bis ${end}). Öffnungszeiten beim Veranstalter prüfen.` : null,
      event.all_day && !visitDay ? "Öffnungszeiten beim Veranstalter prüfen." : null,
      `Quelle: ${event.source_name || "Veranstalter"}${url ? " – "+url : ""}`,
      "Einmalige Kalenderkopie von München Radar. Änderungen und Absagen werden nicht automatisch übernommen."].filter(Boolean).join("\n\n");
    lines.push(`SUMMARY:${escape(event.title)}`,`LOCATION:${escape([event.location_name,event.address].filter(Boolean).join(", "))}`,
      `DESCRIPTION:${escape(description)}`);
    if (url) lines.push(`URL:${url}`);
    // Bookmarks are suggestions, not reservations: don't block the user's availability.
    lines.push("TRANSP:TRANSPARENT","END:VEVENT","END:VCALENDAR");
    return lines.map(fold).join("\r\n")+"\r\n";
  }
  function download(event, visitDay = null) {
    const blob = new Blob([calendar(event, visitDay)], {type:"text/calendar;charset=utf-8"});
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${event.title.replace(/[^\p{L}\p{N} -]/gu, "").slice(0,70) || "Termin"}.ics`;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  return {storageKey, read, toggle, refresh, has:id => saved.has(id), all:() => [...saved.values()],
    issue:() => storageIssue, calendar, download, day, lastDay, safeUrl};
})();
