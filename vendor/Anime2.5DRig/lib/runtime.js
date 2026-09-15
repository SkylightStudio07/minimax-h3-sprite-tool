/* Shared, browser-independent validation and simulation helpers. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RigRuntime = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  const MAX_FILE_BYTES = 128 * 1024 * 1024;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  function validateHeader(buffer) {
    if (!buffer || buffer.byteLength < 26) throw new Error('PSDファイルが短すぎます');
    if (buffer.byteLength > MAX_FILE_BYTES) throw new Error('PSDは128MB以下にしてください');
    const v = new DataView(buffer);
    if (v.getUint32(0) !== 0x38425053 || v.getUint16(4) !== 1) throw new Error('対応するPSDファイルではありません（PSBは未対応）');
    const h = v.getUint32(14), w = v.getUint32(18);
    if (w < 2 || h < 2 || w*h > 24000000 || Math.max(w,h) > 16384) throw new Error('PSDのサイズは一辺16384px・2400万画素以内にしてください');
    if (v.getUint16(22) !== 8 || v.getUint16(24) !== 3) throw new Error('PSDをRGB・8bit/チャンネルで保存し直してください');
    return {w,h};
  }
  function fingerprint(buffer) {
    const b = new Uint8Array(buffer); let a = 2166136261, c = 5381;
    for (let i=0; i<b.length; i++) { a = Math.imul(a ^ b[i], 16777619); c = Math.imul(c, 33) ^ b[i]; }
    return b.length.toString(16)+'-'+(a>>>0).toString(16)+'-'+(c>>>0).toString(16);
  }
  function meshSize(w,h,cell) {
    let nx=Math.max(2,Math.round(w/cell)), ny=Math.max(2,Math.round(h/cell));
    while ((nx+1)*(ny+1)>65000) {
      if(nx>=ny) nx=Math.max(2,Math.floor(nx*0.9)); else ny=Math.max(2,Math.floor(ny*0.9));
    }
    return {nx,ny};
  }
  function spring(s,target,k,damping,dt) {
    const count=Math.max(1,Math.ceil(dt/(1/120))), h=dt/count;
    for(let i=0;i<count;i++){ s.v+=(-k*(s.x-target)-damping*s.v)*h; s.x+=s.v*h; }
  }
  const trackingKeys={ax:[-1,1],ay:[-1,1],az:[-1,1],eL:[0,1],eR:[0,1],mo:[0,1],ex:[-1,1],ey:[-1,1]};
  function tracking(value) {
    if(!value || typeof value.live!=='boolean') return null;
    const out={live:value.live};
    for(const [key,range] of Object.entries(trackingKeys)) {
      if(typeof value[key]!=='number'||!Number.isFinite(value[key]))return null;
      out[key]=clamp(value[key],...range);
    }
    return out;
  }
  function settings(value,modelId,ranges,layerIds) {
    if (!value || value.format!=='anime25d-settings' || value.version!==1) throw new Error('対応する設定ファイルではありません');
    if (value.modelId!==modelId) throw new Error('別のPSD用の設定です。保存時と同じPSDを読み込んでください');
    if(!value.params || !Array.isArray(value.layers) || value.layers.length!==layerIds.length) throw new Error('設定の構造が不正です');
    const out={params:{},auto:{},layers:[],background:'checker',preset:null};
    if(['neutral','smile','usume','surprise','jito','winkL','winkR'].includes(value.preset))out.preset=value.preset;
    for(const [key,range] of Object.entries(ranges)) {
      const n=value.params[key]===undefined&&['clothMotion','legMotion','bodyMotion'].includes(key)?1:value.params[key];
      if(typeof n!=='number'||!Number.isFinite(n)) throw new Error('数値設定が不正です: '+key);
      out.params[key]=clamp(n,...range);
    }
    for(const key of ['idle','blink','rand','talk','mouse','phys']) {
      if(typeof value.auto?.[key]!=='boolean') throw new Error('自動動作の設定が不正です');
      out.auto[key]=value.auto[key];
    }
    const seen=new Set();
    for(const l of value.layers) {
      if(!l || !layerIds.includes(l.id) || seen.has(l.id) || typeof l.visible!=='boolean' ||
        !Number.isFinite(l.opacity) || !Number.isFinite(l.depth)) throw new Error('レイヤー設定が不正です');
      seen.add(l.id); out.layers.push({id:l.id,visible:l.visible,opacity:clamp(l.opacity,0,1),depth:clamp(l.depth,0,2)});
    }
    if(['checker','green','dark'].includes(value.background))out.background=value.background;
    return out;
  }
  // Coordinates are canvas pixels. Scale motion by body height, not face size:
  // full-body illustrations often have a tiny faceScale.
  function idleProfile(parts, anchors, canvasHeight) {
    const grounded=parts.filter(p=>/^(legwear|footwear)(_|$)/.test(p.id));
    const bottom=Math.max(...(grounded.length?grounded:parts).map(p=>p.top+p.height),1);
    const top=Math.min(...parts.map(p=>p.top),bottom-1);
    const height=Math.max(1,bottom-top);
    const clothing=parts.find(p=>p.id==='topwear');
    const pants=parts.find(p=>p.id==='bottomwear');
    const legs=parts.find(p=>p.id==='legwear');
    const waist=pants?pants.top+pants.height*0.28:(legs?legs.top:top+height*0.43);
    const cx=pants?pants.left+pants.width/2:(anchors.neckPivot?.cx||0);
    const coatBottom=clothing&&clothing.top+clothing.height>waist+height*0.22?clothing.top+clothing.height:0;
    const skirt=!!(pants&&pants.height<height*0.32&&pants.width>pants.height*0.8&&
      !(coatBottom&&pants.height<height*0.15)&&
      (!legs||pants.top+pants.height>legs.top+height*0.05));
    return {height,bottom,waist,cx,topTop:clothing?clothing.top:top,
      skirtBottom:skirt?pants.top+pants.height:0,
      coatBottom};
  }
  const ease=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
  function idleOffset(id,x,y,p,phase,strength={}) {
    const h=p.height;
    const cloth=clamp(strength.clothMotion??1,0,2),legs=clamp(strength.legMotion??1,0,2),body=clamp(strength.bodyMotion??1,0,2);
    let dx=0,dy=-h*0.006*body*(0.5+0.5*Math.sin(phase))*ease((p.bottom-y)/(h*0.65));
    const hemBottom=id==='topwear'?p.coatBottom:(id==='bottomwear'?p.skirtBottom:0);
    if(hemBottom){
      const u=clamp((y-p.waist)/Math.max(1,hemBottom-p.waist),0,1);
      const side=clamp((x-p.cx)/(h*0.22),-1,1);
      const wave=Math.sin(phase-side*0.65-u*1.8)+0.24*Math.sin(phase*2-side-u*3.2);
      dx+=h*(id==='topwear'?0.020:0.015)*cloth*u*u*wave;
      dy+=h*0.004*cloth*u*u*Math.sin(phase-side*0.65-u*1.8+0.8);
    }
    // Short jackets/shirts also breathe; pin their shoulder and waist seams.
    if(id==='topwear'||id.startsWith('handwear')){
      const u=clamp((y-p.topTop)/Math.max(1,p.waist-p.topTop),0,1);
      dx+=(x-p.cx)*0.009*cloth*Math.sin(phase-0.4)*Math.sin(Math.PI*u);
    }
    if(id==='topwear'||id.startsWith('handwear')){
      const side=clamp((x-p.cx)/(h*0.12),-1,1);
      const shoulderY=p.waist-h*0.22;
      const weight=ease((Math.abs(x-p.cx)/h-0.085)/0.10)*
        (1-ease((y-p.waist-h*0.07)/(h*0.13)));
      const angle=Math.sin(phase-0.45)*0.020*side*body;
      dx+=-(y-shoulderY)*angle*weight;
      dy+=(x-(p.cx+side*h*0.14))*angle*weight;
    }
    if(id==='legwear'||id==='footwear'||(id==='bottomwear'&&!p.skirtBottom)){
      const u=clamp((y-p.waist)/Math.max(1,p.bottom-p.waist),0,1);
      dx+=h*0.006*legs*Math.sin(phase-0.35)*Math.sin(Math.PI*u);
    }
    return [dx,dy];
  }
  return {MAX_FILE_BYTES,validateHeader,fingerprint,meshSize,spring,tracking,settings,clamp,idleProfile,idleOffset};
});
