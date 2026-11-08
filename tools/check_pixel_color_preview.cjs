const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root='outputs/pixel-color-lock-20261019/';
const page=fs.readFileSync(root+'preview.html','utf8');
const cfg=JSON.parse(page.match(/<script id="configs" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const nodes={};for(const id of ['slider','phase','play','next','previous','zoom','background','speed','colorMode','compare','colorDescription','saveSheet','saveAnimation','saveGif','saveBundle'])nodes[id]={value:id==='speed'?'1':id==='colorMode'?'original':'0',checked:false};
const pictures=['original','palette','stable'].map(method=>({dataset:{method}}));
const cards=['original','palette','stable'].map(colorChoice=>({dataset:{colorChoice},classList:{toggle(){}}}));
const storage=new Map();
const pending=[],styles={},body={dataset:{}};let now=0;
const context={localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},Image:class{},performance:{now:()=>now},requestAnimationFrame:cb=>pending.push(cb),document:{body,documentElement:{style:{setProperty(k,v){styles[k]=v}}},getElementById(id){return id==='configs'?{textContent:JSON.stringify(cfg)}:nodes[id]},querySelectorAll:selector=>selector==='[data-color-choice]'?cards:pictures}};
vm.runInNewContext(fs.readFileSync(root+'preview-script-check.js','utf8'),context);
assert.equal(nodes.colorMode.value,'original');assert.equal(nodes.saveSheet.href,'original/sheet-grid.png');assert.deepEqual(cards.map(c=>c.hidden),[false,true,true]);
for(const mode of ['palette','stable','original']){
 nodes.colorMode.value=mode;nodes.colorMode.onchange();assert.equal(nodes.saveBundle.href,mode+'/assets.zip');assert.equal(nodes.saveAnimation.href,mode+'/animation.png');assert.equal(storage.get('pixel-color-mode-v1'),mode);
 assert.equal(nodes.saveGif.href,mode+'/animation.gif');
 assert.equal(cards.filter(c=>!c.hidden).length,1);assert.equal(cards.find(c=>!c.hidden).dataset.colorChoice,mode);
}
nodes.compare.checked=true;nodes.compare.onchange();assert(cards.every(c=>!c.hidden));
nodes.colorMode.value='unknown';nodes.colorMode.onchange();assert.equal(nodes.colorMode.value,'original');
function agree(i){for(const p of pictures)assert.equal(p.src,p.dataset.method+'/frame-'+String(i).padStart(2,'0')+'.png')}
function tick(t){now=t;pending.splice(0).forEach(cb=>cb(t))}
agree(0);tick(200);assert.notEqual(pictures[0].src,'original/frame-00.png');
nodes.play.onclick();const stopped=pictures.map(p=>p.src);tick(400);assert.deepEqual(pictures.map(p=>p.src),stopped);
nodes.slider.value=String(cfg.indices.length-1);nodes.slider.oninput();agree(cfg.indices.length-1);
nodes.next.onclick();agree(0);nodes.previous.onclick();agree(cfg.indices.length-1);
nodes.slider.value='0';nodes.slider.oninput();nodes.speed.value='2';nodes.play.onclick();tick(500);assert.notEqual(pictures[0].src,'original/frame-00.png');
nodes.zoom.onchange({target:{value:'3'}});assert.equal(styles['--scale'],'3');nodes.background.onchange({target:{value:'light'}});assert.equal(body.dataset.background,'light');
// A chosen mode survives reload; blocked storage still leaves a usable default.
storage.set('pixel-color-mode-v1','stable');vm.runInNewContext(fs.readFileSync(root+'preview-script-check.js','utf8'),{...context});assert.equal(nodes.colorMode.value,'stable');assert.equal(nodes.saveSheet.href,'stable/sheet-grid.png');
nodes.colorMode.value='original';context.localStorage={getItem(){throw Error('disabled')},setItem(){throw Error('disabled')}};vm.runInNewContext(fs.readFileSync(root+'preview-script-check.js','utf8'),{...context});assert.equal(nodes.saveBundle.href,'original/assets.zip');
fs.writeFileSync(root+'preview-behaviour-validation.json',JSON.stringify({passed:true,actualBrowserVerified:false,checks:['Original default, all three choices and matching download links','Show selected or all methods','Saved preference and disabled-storage fallback','Three methods share frame/time','Pause, seek, step and wrap','Speed and resume','Integer zoom and fixed background selector'],method:'Actual preview JavaScript executed in DOM stub'},null,2));
console.log('PASS optional color selection, downloads, preference and synchronized playback in DOM stub');
