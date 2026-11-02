"use strict";
// Image generation is performed by image_gen. This file only copies native
// pixels, finds overlap paths, protects recorded owner regions and cuts tiles.
window.assembleProduction = async (requireComplete = true, exportMaster = true) => {
  const plan = window.job.plan;
  const run = {items:window.job.items};
  const fixedSeams=window.job.fixedSeams?new Map(window.job.fixedSeams.map(s=>[`${s.from}/${s.to}/${s.axis}`,s.path])):null;
  if (requireComplete && (run.items.length !== 75 || run.items.some(i => i.state !== 'generated' || !i.nativeRegistrationMatches)))
    throw Error('All 75 registered native originals are required before assembly.');
  const [width, height] = plan.imageSize, size = plan.renderSize, overlap = plan.adjacentOverlap;
  const master = canvas(width, height), ctx = master.getContext('2d', {willReadFrequently:true});
  const completed = new Set(), seams = [];
  const items = run.items.filter(i => i.state === 'generated').sort((a,b) => a.tile.row-b.tile.row || a.tile.col-b.tile.col);
  const ownerById = new Map(items.map(i => [i.id,i]));
  // Two padded allowances overlap by 1.45 source pixels at Alte Pinakothek.
  // Resolve raster rounding within that padding, preserving both footprints.
  // Retain the exact source plan and record this registration decision.
  const protectionAdjustments=[];
  plan.landmarks=plan.landmarks.map(p=>({...p,protectedRect:p.protectedRect.map((v,n)=>n<2?Math.floor(v):Math.ceil(v))}));
  for(let i=0;i<plan.landmarks.length;i++)for(const b of plan.landmarks.slice(i+1)){
    const a=plan.landmarks[i];if(a.owner===b.owner)continue;
    const A=a.protectedRect,B=b.protectedRect;
    const w=Math.min(A[2],B[2])-Math.max(A[0],B[0]),h=Math.min(A[3],B[3])-Math.max(A[1],B[1]);
    if(w<=0||h<=0)continue;
    let p,index,value;
    if(w<=4){p=a.masterPixel[0]<b.masterPixel[0]?a:b;index=2;value=Math.max(A[0],B[0]);}
    else if(h<=4){p=a.masterPixel[1]<b.masterPixel[1]?a:b;index=3;value=Math.max(A[1],B[1]);}
    else throw Error(`Conflicting landmark ownership: ${a.id}, ${b.id}`);
    const original=[...p.protectedRect];p.protectedRect[index]=value;
    const fp=p.footprint;
    const extent=fp?[(fp[0]-plan.bounds[0])*plan.scale,(plan.bounds[3]-fp[3])*plan.scale,
      (fp[2]-plan.bounds[0])*plan.scale,(plan.bounds[3]-fp[1])*plan.scale]:[...p.masterPixel,...p.masterPixel];
    if(p.protectedRect[0]>extent[0]||p.protectedRect[1]>extent[1]||p.protectedRect[2]<extent[2]||p.protectedRect[3]<extent[3])
      throw Error(`Protection adjustment intersects a footprint: ${p.id}`);
    protectionAdjustments.push({id:p.id,neighbor:p===a?b.id:a.id,originalRect:original,effectiveRect:[...p.protectedRect],
      reason:'Trim at most four pixels from overlapping padded allowances; no building footprint changes.'});
  }
  function path(A,B,horizontal) {
    const length = size, span = overlap, costs = new Float64Array(length*span), parents = new Int16Array(length*span);
    for (let t=0;t<length;t++) for (let s=0;s<span;s++) {
      const x=horizontal?t:s,y=horizontal?s:t,k=(y*size+x)*4;
      let error=0;
      if (A[k+3]) for(let c=0;c<3;c++) error+=Math.abs(A[k+c]-B[k+c]);
      const index=t*span+s;
      if (!t) {costs[index]=error;continue;}
      let best=Infinity,previous=s;
      for(let d=-1;d<=1;d++) if(s+d>=0&&s+d<span) {
        const candidate=costs[index-span+d]+(d?2:0);
        if(candidate<best){best=candidate;previous=s+d;}
      }
      costs[index]=best+error;parents[index]=previous;
    }
    let s=0;
    for(let n=1;n<span;n++)if(costs[(length-1)*span+n]<costs[(length-1)*span+s])s=n;
    const result=new Int16Array(length);
    for(let t=length-1;t>=0;t--){result[t]=s;s=parents[t*span+s];}
    return result;
  }
  function fixedPath(from,to,axis,A,B,horizontal){
    if(!fixedSeams)return path(A,B,horizontal);
    const p=fixedSeams.get(`${from}/${to}/${axis}`);
    if(!p||p.length!==size||p.some(v=>!Number.isInteger(v)||v<0||v>=overlap))throw Error('Frozen overlap path is absent or invalid');
    return Int16Array.from(p);
  }
  for (const item of items) {
    const source=await image(item.url);
    if(source.width!==size||source.height!==size)throw Error(`Native size changed: ${item.id}`);
    const [ox,oy]=item.tile.renderOrigin;
    const local=canvas(size),lctx=local.getContext('2d',{willReadFrequently:true});
    lctx.drawImage(master,-ox,-oy);const A=lctx.getImageData(0,0,size,size);
    lctx.clearRect(0,0,size,size);lctx.drawImage(source,0,0);const B=lctx.getImageData(0,0,size,size);
    const left=items.find(p=>p.tile.row===item.tile.row&&p.tile.col===item.tile.col-1&&completed.has(p.id));
    const top=items.find(p=>p.tile.col===item.tile.col&&p.tile.row===item.tile.row-1&&completed.has(p.id));
    const vertical=left?fixedPath(left.id,item.id,'vertical',A.data,B.data,false):null,horizontal=top?fixedPath(top.id,item.id,'horizontal',A.data,B.data,true):null;
    const forced=new Int8Array(size*size);
    for(const landmark of plan.landmarks) {
      const owner=landmark.owner;
      if(owner!==item.id&&!completed.has(owner))continue;
      const [a,b,c,d]=landmark.protectedRect;
      const x0=Math.max(0,Math.floor(a-ox)),y0=Math.max(0,Math.floor(b-oy));
      const x1=Math.min(size,Math.ceil(c-ox)),y1=Math.min(size,Math.ceil(d-oy));
      for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)forced[y*size+x]=owner===item.id?1:-1;
    }
    for(let y=0;y<size;y++)for(let x=0;x<size;x++) {
      const i=y*size+x,k=i*4;
      if(!A.data[k+3])continue;
      let weight=1;
      if(vertical&&x<overlap)weight=Math.min(weight,Math.max(0,Math.min(1,(x-vertical[y]+2)/4)));
      if(horizontal&&y<overlap)weight=Math.min(weight,Math.max(0,Math.min(1,(y-horizontal[x]+2)/4)));
      if(forced[i])weight=forced[i]>0?1:0;
      for(let channel=0;channel<4;channel++)B.data[k+channel]=Math.round(A.data[k+channel]*(1-weight)+B.data[k+channel]*weight);
    }
    lctx.putImageData(B,0,0);ctx.drawImage(local,ox,oy);completed.add(item.id);
    if(vertical)seams.push({from:left.id,to:item.id,axis:'vertical',origin:[ox,oy],path:Array.from(vertical)});
    if(horizontal)seams.push({from:top.id,to:item.id,axis:'horizontal',origin:[ox,oy],path:Array.from(horizontal)});
    source.src='';local.width=local.height=1;
  }
  const protectedChecks=[];
  for(const p of plan.landmarks){
    const owner=ownerById.get(p.owner);if(!owner){if(requireComplete)throw Error('Landmark owner absent');else continue;}
    const source=await image(owner.url),[ox,oy]=owner.tile.renderOrigin;
    const [a,b,c,d]=p.protectedRect.map((v,n)=>n<2?Math.floor(v):Math.ceil(v));
    const test=canvas(c-a,d-b),tctx=test.getContext('2d');tctx.drawImage(source,ox-a,oy-b);
    const expected=tctx.getImageData(0,0,c-a,d-b).data,actual=ctx.getImageData(a,b,c-a,d-b).data;
    let difference=0;for(let n=0;n<actual.length;n++)difference=Math.max(difference,Math.abs(expected[n]-actual[n]));
    protectedChecks.push({id:p.id,owner:p.owner,maxChannelDifference:difference});
    source.src='';test.width=test.height=1;
  }
  if(protectedChecks.some(p=>p.maxChannelDifference))throw Error('Protected owner pixels changed during assembly.');
  window.productionMaster=master;
  const preview=canvas(1800,Math.round(1800*height/width));
  preview.getContext('2d').drawImage(master,0,0,preview.width,preview.height);
  return {master:exportMaster?master.toDataURL('image/png'):null,preview:preview.toDataURL('image/png'),width,height,
    sources:items.map(i=>({id:i.id,sha256:i.outputSha256,origin:i.tile.renderOrigin})),
    sourceResampleFactor:1,overlap,blendPixels:4,seams,protectedChecks,protectionAdjustments,
    protectedRegions:plan.landmarks.map(p=>({id:p.id,owner:p.owner,rect:p.protectedRect}))};
};
window.productionTiles=(z,row)=>{
  const k=2**z,w=productionMaster.width*k,h=productionMaster.height*k,images={};
  for(let x=0;x<Math.ceil(w/256);x++){
    const c=canvas(256),ctx=c.getContext('2d');ctx.imageSmoothingQuality='high';
    if(z===0)ctx.drawImage(productionMaster,-x*256,-row*256);
    else ctx.drawImage(productionMaster,-x*256,-row*256,w,h);
    images[`${z}/${x}/${row}`]=c.toDataURL('image/png');
  }
  return images;
};
window.composeCandidate=async job=>{
  const base=await image(job.base),raw=await image(job.raw),size=base.width;
  if(size!==1254||base.height!==size||raw.width!==size||raw.height!==size)throw Error('Native source size changed');
  const c=canvas(size),ctx=c.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(base,0,0);const A=ctx.getImageData(0,0,size,size);
  ctx.clearRect(0,0,size,size);ctx.drawImage(raw,0,0);const B=ctx.getImageData(0,0,size,size);
  const [a,b,d,e]=job.rect,f=job.feather;
  for(let y=b;y<e;y++)for(let x=a;x<d;x++){
    const weight=Math.max(0,Math.min(1,a>0?(x-a+1)/f:1,b>0?(y-b+1)/f:1,d<size?(d-x)/f:1,e<size?(e-y)/f:1));
    const k=(y*size+x)*4;
    for(let n=0;n<4;n++)A.data[k+n]=Math.round(A.data[k+n]*(1-weight)+B.data[k+n]*weight);
  }
  ctx.putImageData(A,0,0);return c.toDataURL('image/png');
};

window.applyCloudFrame=async recipe=>{
  const textures=await Promise.all((recipe.textures||[recipe.texture]).map(image)),texture=textures[0],mask=await image(recipe.mask);
  const master=window.productionMaster,w=master.width,h=master.height;
  if(texture.width!==recipe.nativeSize[0]||texture.height!==recipe.nativeSize[1]||mask.width!==w||mask.height!==h)
    throw Error('Cloud frame dimensions changed');
  const clouds=canvas(w,h),ctx=clouds.getContext('2d');
  if(textures.some(t=>t.width!==texture.width||t.height!==texture.height))throw Error('Cloud variant dimensions changed');
  const tw=texture.width,th=texture.height,f=recipe.overlap,stepX=tw-2*f,stepY=th-2*f;
  let seed=recipe.seed||73109;
  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  // Opaque underpainting guarantees a complete rectangle. Staggered, jittered
  // native sheets above it have feathered edges and no mirror-fold symmetry.
  for(let y=0;y<h;y+=th)for(let x=0;x<w;x+=tw)ctx.drawImage(textures[Math.floor(random()*textures.length)],x,y);
  let placements=0;
  for(let row=0,baseY=-f;baseY<h;row++,baseY+=stepY){
    const shift=Math.floor(random()*stepX);
    for(let col=0,baseX=-shift-f;baseX<w;col++,baseX+=stepX){
      const x=baseX+Math.floor(random()*f)-f/2,y=baseY+Math.floor(random()*f)-f/2;
      const patch=canvas(tw,th),p=patch.getContext('2d');
      p.drawImage(textures[Math.floor(random()*textures.length)],0,0);
      p.globalCompositeOperation='destination-in';
      const horizontal=p.createLinearGradient(0,0,tw,0);
      horizontal.addColorStop(0,'transparent');horizontal.addColorStop(f/tw,'black');horizontal.addColorStop(1-f/tw,'black');horizontal.addColorStop(1,'transparent');
      p.fillStyle=horizontal;p.fillRect(0,0,tw,th);
      const vertical=p.createLinearGradient(0,0,0,th);
      vertical.addColorStop(0,'transparent');vertical.addColorStop(f/th,'black');vertical.addColorStop(1-f/th,'black');vertical.addColorStop(1,'transparent');
      p.fillStyle=vertical;p.fillRect(0,0,tw,th);
      ctx.drawImage(patch,x,y);patch.width=patch.height=1;placements++;
    }
  }
  const cover=canvas(w,h),c=cover.getContext('2d');
  c.drawImage(clouds,0,0);c.globalCompositeOperation='destination-in';c.drawImage(mask,0,0);
  ctx.drawImage(master,0,0);
  const out=master.getContext('2d');out.clearRect(0,0,w,h);out.drawImage(clouds,0,0);out.drawImage(cover,0,0);
  clouds.width=clouds.height=cover.width=cover.height=1;
  return {nativeSize:recipe.nativeSize,sourceResampleFactor:1,placements,textureCount:textures.length,seed:recipe.seed||73109,rectangle:[w,h]};
};
