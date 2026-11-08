const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=(process.argv[2]||'outputs/pixel-attack-actions-20261019').replace(/[\\/]+$/,'')+'/';
const page=fs.readFileSync(root+'preview.html','utf8');
const configs=JSON.parse(page.match(/<script id="configs" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const nodes={},styles={},body={dataset:{}};let now=0;const pending=[];
for(const c of configs){
 const item={};for(const name of ['frame','phase','slider','play','previous','next','speed'])item[name]={value:name==='speed'?'1':'0'};
 nodes[c.id]={item,querySelector(selector){if(selector==='[data-frame]')return item.frame;if(selector==='[data-phase]')return item.phase;return item[selector.match(/"(.*?)"/)[1]]}};
}
nodes.zoom={};nodes.background={};
const context={
 Image:class{},performance:{now:()=>now},requestAnimationFrame:cb=>pending.push(cb),
 document:{body,documentElement:{style:{setProperty(k,v){styles[k]=v}}},
 getElementById(id){return id==='configs'?{textContent:JSON.stringify(configs)}:nodes[id]}}
};
vm.runInNewContext(fs.readFileSync(root+'preview-script-check.js','utf8'),context);
function tick(t){now=t;pending.splice(0).forEach(cb=>cb(t))}
for(const c of configs)assert.equal(nodes[c.id].item.frame.src,c.id+'/frame-00.png');
tick(200);
for(const c of configs)assert.notEqual(nodes[c.id].item.frame.src,c.id+'/frame-00.png');
const spin=nodes[configs[0].id].item;
spin.play.onclick();const stopped=spin.frame.src;tick(400);assert.equal(spin.frame.src,stopped);
for(const c of configs){
 const e=nodes[c.id].item;e.slider.value=String(c.indices.length-1);e.slider.oninput();
 assert.equal(e.frame.src,c.id+'/frame-'+String(c.indices.length-1).padStart(2,'0')+'.png');
 e.next.onclick();assert.equal(e.frame.src,c.id+'/frame-00.png');e.previous.onclick();
 assert.equal(e.frame.src,c.id+'/frame-'+String(c.indices.length-1).padStart(2,'0')+'.png');
 e.slider.value='0';e.slider.oninput();e.speed.value='2';e.play.onclick();
}
tick(500);for(const c of configs)assert.notEqual(nodes[c.id].item.frame.src,c.id+'/frame-00.png');
nodes.zoom.onchange({target:{value:'3'}});assert.equal(styles['--scale'],'3');
nodes.background.onchange({target:{value:'checker'}});assert.equal(body.dataset.background,'checker');
const result={passed:true,actualBrowserVerified:false,players:configs.length,checks:['Action players initialize and advance','Independent pause','Seek, previous, next and wrap','Resume and speed','Integer zoom and background selection'],method:'Execute actual preview JavaScript in DOM stub'};
fs.writeFileSync(root+'preview-behaviour-validation.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
