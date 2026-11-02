  let map, cluster, loading, renderVersion = 0, labelItems = [], frame = 0, state = null;
  let markers = new Map(), viewKey = "";
  function position(place) { return window.RadarAtlas.position(place); }
  function resetView() { if (map) window.RadarAtlas.home(); }
  function fitAll() { if (map) window.RadarAtlas.overview(); }
  function asset(tag, src) {
    return new Promise((resolve,reject) => {
      const el = document.createElement(tag);
      if(tag === "script") el.src=src; else {el.rel="stylesheet";el.href=src;}
      el.onload=resolve;el.onerror=()=>{el.remove();reject(Error("Kartenbestandteile nicht verfügbar"));};
      document.head.append(el);
    });
  }
  async function initialize() {
    if(loading) return loading;
    loading = (async () => {
      await Promise.all([
        window.RadarAtlas.ready,
        asset("link","./vendor/leaflet/leaflet.css"),
        asset("link","./vendor/leaflet.markercluster/MarkerCluster.css"),
        asset("link","./vendor/leaflet.markercluster/MarkerCluster.Default.css"),
        window.L ? Promise.resolve() : asset("script","./vendor/leaflet/leaflet.js")
      ]);
      if(!L.markerClusterGroup) await asset("script","./vendor/leaflet.markercluster/leaflet.markercluster.js");
      map = window.RadarAtlas.create("event-map");
      cluster=L.markerClusterGroup({maxClusterRadius:38,disableClusteringAtZoom:map.getMaxZoom(),animate:false,showCoverageOnHover:false,
        iconCreateFunction:group=>L.divIcon({html:`<span>${group.getAllChildMarkers().reduce((n,m)=>n+m.options.eventCount,0)}</span>`,className:"isar-cluster",iconSize:[46,46]})});
      map.addLayer(cluster);
      map.on("move zoom resize moveend zoomend", layout);
      new ResizeObserver(()=>{map.invalidateSize({pan:true,animate:false});layout();}).observe(stage);
      stage.dataset.mapReady="true";
      const note=node("p","atlas-scope","");
      const sub=node("span","","");
      note.append(sub); infoBody.prepend(note);
      const packageLabel=node("label","atlas-package-label","Kartenansicht");
      const packageSelect=node("select","");packageSelect.id="atlas-package-select";
      for(const item of RadarAtlas.packages()){
        const option=node("option","",item.title);option.value=item.id;packageSelect.append(option);
      }
      const packageStatus=node("p","atlas-package-status","");packageStatus.setAttribute("role","status");
      packageLabel.append(packageSelect);infoBody.prepend(packageLabel,packageStatus);
      const updatePackage=()=>{
        const active=RadarAtlas.active(),whole=active.coverage==="full-city";
        packageSelect.value=active.id;
        note.firstChild?.nodeType===3&&note.firstChild.remove();
        note.prepend(document.createTextNode(whole?"Illustrierte Karte für ganz München":active.title));
        sub.textContent=whole?"Die Karte lässt sich unabhängig von deinen Terminen und Filtern austauschen.":"Außerhalb der Illustration zeigt diese Studie die Stadtvorlage.";
        smallNote.textContent=whole?"München · illustriert · Lage vereinfacht":"Innenstadt · native Bilddetails";
        if(active.fallbackReason)packageStatus.textContent=active.fallbackReason;
      };
      updatePackage();
      packageSelect.addEventListener("change",async()=>{
        packageSelect.disabled=true;packageStatus.textContent="Karte wird geladen …";
        try{await RadarAtlas.switchMap(packageSelect.value);packageStatus.textContent="Kartenansicht gewechselt.";}
        catch{packageSelect.value=RadarAtlas.active().id;packageStatus.textContent="Diese Karte konnte nicht geladen werden. Die bisherige Ansicht bleibt erhalten.";}
        finally{packageSelect.disabled=false;}
      });
      window.addEventListener("atlas:changed",()=>{
        updatePackage();
        cluster.remove();
        cluster=L.markerClusterGroup({maxClusterRadius:38,disableClusteringAtZoom:map.getMaxZoom(),animate:false,showCoverageOnHover:false,
          iconCreateFunction:group=>L.divIcon({html:`<span>${group.getAllChildMarkers().reduce((n,m)=>n+m.options.eventCount,0)}</span>`,className:"isar-cluster",iconSize:[46,46]})}).addTo(map);
        RadarMap.show(state?.candidates||[],null,"map-package-change").catch(()=>{packageStatus.textContent="Orte konnten nicht neu angezeigt werden.";});
      });
      const comparison=node("p","atlas-comparison","Bildvergleich: ");
      for(const [title,url]of[["Aktuelle Karte","/?map=painted"],["Originalkarte","/?map=baseline"]]){
        const link=node("a","",title);link.href=url;comparison.append(link,document.createTextNode(" · "));
      }
      infoBody.prepend(comparison);
      const artwork=button("Karte pur","prototype-map-button",()=>{
        const clean=stage.classList.toggle("atlas-artwork-only");
        artwork.textContent=clean?"Termine zeigen":"Karte pur";artwork.setAttribute("aria-pressed",String(clean));
      });
      artwork.setAttribute("aria-pressed","false");mapTools.append(artwork);
      const outside=node("div","atlas-outside","Stadtvorlage · dieser Bereich ist noch nicht illustriert");
      outside.hidden=true;stage.append(outside);window.RadarAtlas.setScopeNotice(outside);
      window.__atlasReady=true;
    })().catch(error=>{loading=null;throw error;});
    return loading;
  }
