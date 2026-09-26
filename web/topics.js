"use strict";
window.RadarTopics = (() => {
  const labels = {all:"Alles",music:"Musik",food:"Food",art:"Kunst",shopping:"Shopping & Märkte",stage:"Bühne",outdoor:"Draußen",science:"Wissen"};
  const cache = new WeakMap();
  function classify(event) {
    if (cache.has(event)) return cache.get(event);
    const tags = new Set([event.category,...(event.tags || [])]);
    const title = String(event.title || "").normalize("NFKC").toLocaleLowerCase("de");
    const venue = `${event.source_name || ""} ${event.location_name || ""}`.toLocaleLowerCase("de");
    const has = (...values) => values.some(value => tags.has(value));
    const topics = new Set();
    if (has("concert","music") || /konzert|jazz|livemusik|live-musik|kammermusik|chorabend|musical|oper\b/.test(title)) topics.add("music");
    // Explicit culinary titles/tags, not incidental words in descriptions or all markets.
    if (has("food") || /bauernmarkt|wochenmarkt|street[ -]?food|food.?festival|kulinar|genussmarkt|wein(fest|probe|verkostung)|bier(fest|verkostung)|koch(kurs|workshop)|käsemarkt/.test(title)) topics.add("food");
    if (has("art") || /lenbachhaus|pinakothek|museum brandhorst|sammlung schack|haus der kunst/.test(venue)
        || /kunstausstellung|kunstführung|galerie|vernissage|malworkshop|zeichenworkshop/.test(title)
        || (has("exhibition") && !has("science","technology"))) topics.add("art");
    if (has("shopping","market","flea_market") || /markt|shopping|verkaufsoffen/.test(title)) topics.add("shopping");
    if (has("theatre") || /theater|kabarett|comedy|ballett|oper\b|musical/.test(title)) topics.add("stage");
    if (has("outdoor","street_festival") || /open[ -]?air|straßenfest|strassenfest|wanderung|spaziergang/.test(title)) topics.add("outdoor");
    if (has("science","technology") || /wissenschaft|robotik|astronomie|planetarium/.test(title)) topics.add("science");
    cache.set(event,topics); return topics;
  }
  return {labels,classify,matches:(event,topic) => topic === "all" || classify(event).has(topic)};
})();
