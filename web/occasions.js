"use strict";
window.RadarOccasions = (() => {
  const key = value => String(value || "").normalize("NFKC").toLocaleLowerCase("de").replace(/[^\p{L}\p{N}_]+/gu," ").trim();
  const matches = (event, rule) => (rule.keywords || []).some(word => key(event.title).includes(key(word)))
    || (event.tags || []).some(tag => (rule.tags || []).includes(tag));
  function active(rules, events, today, onDay) {
    return rules.filter(rule => {
      if (rule.window) {
        const day = today.slice(5), {start,end} = rule.window;
        return start <= end ? start <= day && day <= end : day >= start || day <= end;
      }
      const anchors = (rule.anchor_titles || []).map(key);
      return events.some(event => !event.stale && event.status === "scheduled"
        && ["festival","street_festival","seasonal"].includes(event.category)
        && anchors.includes(key(event.title.replace(/\b20\d{2}\b/g,""))) && onDay(event,today));
    });
  }
  return {active,matches};
})();
