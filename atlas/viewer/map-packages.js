"use strict";
// Map-package adapter. Application selection, persistence and exports live elsewhere.
window.RadarAtlas=(()=>{
  let config,map,notice,tiles,contextLayers,frame,registry,changeVersion=0;
  const R=6378137;
  const project=(lon,lat)=>[R*lon*Math.PI/180,R*Math.log(Math.tan(Math.PI/4+lat*Math.PI/360))];
  const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
  const safePath=value=>{
    if(typeof value!=="string"||!value||value.startsWith("/")||value.split("/").includes("..")||!/^[a-zA-Z0-9_./-]+$/.test(value))throw Error("Ungültiger Kartenpfad");
    return value;
  };
  const assetURL=path=>`/atlas/${safePath(path)}`;
  const json=async path=>{const r=await fetch(assetURL(path));if(!r.ok)throw Error("Kartenpaket konnte nicht geladen werden");return r.json();};
  function validate(raw,entry){
    if(!raw||typeof raw!=="object"||(raw.packageVersion!==undefined&&raw.packageVersion!==1))throw Error("Unbekanntes Kartenformat");
    if(!finite(raw.cityBounds,4)||raw.cityBounds[0]>=raw.cityBounds[2]||raw.cityBounds[1]>=raw.cityBounds[3])throw Error("Ungültige Kartengrenzen");
    if(!finite(raw.patchOrigin,2)||!Number.isFinite(raw.scale)||raw.scale<=0)throw Error("Ungültige Kartenkoordinaten");
    const imageSize=raw.imageSize||[raw.patchSize,raw.patchSize];
    if(!finite(imageSize,2)||imageSize.some(v=>v<=0))throw Error("Ungültige Bildgröße");
    if(!Array.isArray(raw.worldBounds)||raw.worldBounds.length!==2||raw.worldBounds.some(p=>!finite(p,2))||raw.worldBounds[0][0]>=raw.worldBounds[1][0]||raw.worldBounds[0][1]>=raw.worldBounds[1][1])throw Error("Ungültiger Kartenausschnitt");
    const axisScale=raw.axisScale||[raw.scale,raw.scale];
    if(!finite(axisScale,2)||axisScale.some(s=>s<=0))throw Error("Ungültiger Kartenmaßstab");
    if(!Number.isInteger(raw.tileMinZoom)||raw.tileMinZoom>0||!Number.isFinite(raw.closestZoom)||raw.closestZoom>0)throw Error("Ungültige Zoomgrenzen");
    if(!Array.isArray(raw.tileKeys)||!raw.tileKeys.length||raw.tileKeys.some(k=>typeof k!=="string"||!/^[-]?\d+\/[-]?\d+\/[-]?\d+$/.test(k)))throw Error("Ungültiges Kachelverzeichnis");
    const tileFormat=raw.tileFormat||"webp";
    if(!["png","webp"].includes(tileFormat))throw Error("Unbekanntes Bildformat");
    if(raw.rotation!==false||raw.orientation!=="north-up")throw Error("Das Kartenpaket muss nordorientiert sein");
    const anchors=raw.anchors||{};
    if(Object.values(anchors).some(p=>!finite(p,2)||p.some(v=>v<0||v>1)))throw Error("Ungültige Ortsanker");
    const tileBase=safePath(raw.tileBase||"tiles");
    return {...raw,id:entry.id,title:entry.title,imageSize,axisScale,tileFormat,tileBase,anchors,coverage:raw.coverage||"partial"};
  }
  const tileURL=(c,key)=>assetURL(`${c.tileBase}/${key}.${c.tileFormat}`);
  async function loadPackage(id){
    const entry=registry.maps.find(e=>e.id===id);
    if(!entry)throw Error("Unbekannte Karte");
    const c=validate(await json(entry.manifest),entry);
    await new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>i.naturalWidth===256&&i.naturalHeight===256?resolve():reject(Error("Ungültige Kachelgröße"));i.onerror=()=>reject(Error("Kartenbilder konnten nicht geladen werden"));i.src=tileURL(c,c.tileKeys[0]);});
    return c;
  }
  const ready=(async()=>{
    registry=await json("maps/registry.json");
    if(!Array.isArray(registry.maps)||!registry.maps.length)throw Error("Kartenverzeichnis fehlt");
    const params=new URLSearchParams(location.search),release=params.get("release");
    if(release){
      if(!/^[a-f0-9]{16}(-[a-f0-9]{6})?$/.test(release))throw Error("Ungültige Vorschauversion");
      registry.maps.push({id:"preview",title:"Kachelvorschau",manifest:`releases/${release}/manifest.json`});
    }
    const requested=release?"preview":params.get("map")||params.get("art")||registry.default;
    try{config=await loadPackage(requested);}catch(error){
      if(requested==="baseline")throw error;
      config=await loadPackage("baseline");config.fallbackReason="Die gewählte Karte ist nicht verfügbar. Die Originalkarte bleibt nutzbar.";
    }
    return config;
  })();
  const pixel=(p,c=config)=>[(p[0]-c.cityBounds[0])*c.axisScale[0],(c.cityBounds[3]-p[1])*c.axisScale[1]];
  function position(place){
    const override=config.anchors[place.id];
    const xy=override?[config.patchOrigin[0]+override[0]*config.imageSize[0],config.patchOrigin[1]+override[1]*config.imageSize[1]]:pixel(project(place.lon,place.lat));
    return [-xy[1],xy[0]];
  }
  const artworkBounds=()=>L.latLngBounds([
    [-config.patchOrigin[1]-config.imageSize[1],config.patchOrigin[0]],[-config.patchOrigin[1],config.patchOrigin[0]+config.imageSize[0]]
  ]);
  function home(){
    if(!map)return;
    const xy=config.home?pixel(project(config.home.lon,config.home.lat)):[config.patchOrigin[0]+config.imageSize[0]*.53,config.patchOrigin[1]+config.imageSize[1]*.51];
    map.setView([-xy[1],xy[0]],map.getMaxZoom(),{animate:false});sync();
  }
  function overview(){if(map){updateMin();map.fitBounds(config.worldBounds,{padding:[24,24],animate:false,maxZoom:config.closestZoom});sync();}}
  function sync(){
    if(!map||!config)return;
    if(notice)notice.hidden=config.coverage==="full-city"||(artworkBounds().contains(map.getCenter())&&map.getZoom()>map.getMinZoom()+.5);
    document.querySelectorAll(".leaflet-control-zoom-in").forEach(el=>{el.title=config.version>=2?"Native Bilddetails":"Nächste Ansicht";});
    window.__atlasState={id:config.id,coverage:config.coverage,zoom:map.getZoom(),minZoom:map.getMinZoom(),maxZoom:map.getMaxZoom(),bearing:0,rotationEnabled:false,
      tileCount:config.tileKeys.length,patchSize:config.patchSize,imageSize:config.imageSize,worldBounds:config.worldBounds,patchBounds:artworkBounds().toBBoxString(),
      center:map.getCenter(),anchors:config.anchors,variant:config.variant||config.id,nativePixelScale:config.sourcePixelScale||null};
  }
  function tileLayer(c){
    const keys=new Set(c.tileKeys);
    const LocalTiles=L.GridLayer.extend({createTile(coords,done){
      const key=`${coords.z}/${coords.x}/${coords.y}`;
      if(!keys.has(key)){const blank=document.createElement("canvas");blank.width=blank.height=256;queueMicrotask(()=>done(null,blank));return blank;}
      const tile=document.createElement("img");tile.alt="";tile.role="presentation";
      tile.onload=()=>done(null,tile);
      tile.onerror=()=>{document.querySelector("#map-tile-notice").hidden=false;done(Error("Atlasbild fehlt"),tile);};
      tile.src=tileURL(c,key);return tile;
    }});
    return new LocalTiles({tileSize:256,minNativeZoom:c.tileMinZoom,maxNativeZoom:0,minZoom:-12,maxZoom:c.closestZoom,noWrap:true,keepBuffer:2,pane:"tilePane"});
  }
  function updateMin(){
    // getBoundsZoom clamps to the existing minimum, preventing a narrower
    // viewport from lowering that minimum. Compute the fit independently.
    const size=map.getSize(),bounds=L.latLngBounds(config.worldBounds),snap=map.options.zoomSnap||1;
    const scale=Math.min(Math.max(1,size.x-48)/(bounds.getEast()-bounds.getWest()),Math.max(1,size.y-48)/(bounds.getNorth()-bounds.getSouth()));
    map.setMinZoom(Math.min(config.closestZoom,Math.floor(Math.log2(scale)/snap)*snap));
  }
  function install(next,previousCamera){
    if(tiles)map.removeLayer(tiles);
    if(contextLayers)map.removeLayer(contextLayers);
    if(frame)map.removeLayer(frame);
    config=next;window.__atlasConfig=config;
    map.setMaxZoom(config.closestZoom);map.options.zoomSnap=config.version>=2?1:.125;map.options.zoomDelta=config.version>=2?1:.5;
    map.setMaxBounds(config.worldBounds);updateMin();
    contextLayers=L.layerGroup().addTo(map);
    if(config.cityOutline?.length){
      const city=config.cityOutline.map(ring=>ring.map(p=>{const[x,y]=pixel(p);return[-y,x];}));
      L.polygon(city,{pane:"atlas-context",color:"#b7bba2",weight:1,fillColor:"#e6e7d7",fillOpacity:1,interactive:false}).addTo(contextLayers);
    }
    for(const area of config.context||[]){
      const [x,y]=pixel(project(area.lon,area.lat)),label=document.createElement("span");label.textContent=area.name;
      L.marker([-y,x],{interactive:false,keyboard:false,icon:L.divIcon({className:"atlas-context-label",html:label,iconSize:[130,24]})}).addTo(contextLayers);
    }
    document.querySelector("#event-map").dataset.artReady="false";
    tiles=tileLayer(config)
      .on("loading",()=>{document.querySelector("#event-map").dataset.artReady="false";})
      .on("load",()=>{document.querySelector("#event-map").dataset.artReady="true";}).addTo(map);
    window.__atlasTiles=tiles;
    if(config.coverage!=="full-city")frame=L.rectangle(artworkBounds(),{color:"#697957",weight:1,dashArray:"5 7",fill:false,interactive:false}).addTo(map);else frame=null;
    if(previousCamera){
      const [x,y]=pixel(previousCamera.point),z=Math.max(map.getMinZoom(),Math.min(config.closestZoom,previousCamera.zoom+Math.log2(previousCamera.scale/config.scale)));
      map.setView([-y,x],z,{animate:false});
    }else if(config.initialView==="overview")overview();else home();
    sync();
  }
  async function switchMap(id){
    const version=++changeVersion,next=await loadPackage(id);
    if(version!==changeVersion)return false;
    if(!map){config=next;return true;}
    const center=map.getCenter(),previousCamera={point:[config.cityBounds[0]+center.lng/config.axisScale[0],config.cityBounds[3]+center.lat/config.axisScale[1]],zoom:map.getZoom(),scale:config.scale};
    install(next,previousCamera);
    const url=new URL(location.href);url.searchParams.delete("art");url.searchParams.set("map",id);history.replaceState(null,"",url);
    window.dispatchEvent(new CustomEvent("atlas:changed",{detail:{id,title:config.title,coverage:config.coverage}}));
    return true;
  }
  function create(id){
    map=L.map(id,{crs:L.CRS.Simple,minZoom:-8,maxZoom:config.closestZoom,zoomSnap:config.version>=2?1:.125,zoomDelta:config.version>=2?1:.5,
      scrollWheelZoom:true,tapHold:true,preferCanvas:true,fadeAnimation:false,attributionControl:false,maxBoundsViscosity:1});
    map.createPane("atlas-context");map.getPane("atlas-context").style.zIndex=180;
    install(config);map.on("resize",updateMin);map.on("moveend zoomend",sync);
    window.__atlasMap=map;return map;
  }
  return {ready,position,create,home,overview,sync,switchMap,
    packages(){return registry.maps.filter(e=>!e.hidden).map(({id,title})=>({id,title}));},
    active(){return {id:config.id,title:config.title,coverage:config.coverage,fallbackReason:config.fallbackReason};},
    setScopeNotice(el){notice=el;sync();}};
})();

