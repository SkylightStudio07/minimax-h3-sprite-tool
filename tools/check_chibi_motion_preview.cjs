// Exercise the actual exported player script without claiming browser rendering QA.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=process.argv[2]?path.resolve(process.argv[2]):path.resolve(__dirname,'../outputs/chibi-motion-20261020');
const source=fs.readFileSync(path.join(root,'preview-script.js'),'utf8');
const data=JSON.parse(source.match(/^const data=(.*?);const states=/s)[1]);
assert.deepStrictEqual(Object.keys(data).sort(),process.argv[3]?process.argv[3].split(',').sort():['idle','walk']);
const roots={},top={zoom:{},background:{}},queue=[];
for(const name of Object.keys(data)){
 const controls={};for(const key of ['.player','.seek','.play','.position','.prev','.next','.speed'])controls[key]={};
 roots[name]={controls,querySelector:key=>{assert(controls[key],key);return controls[key]}};
 const metadataPath=fs.existsSync(path.join(root,name,'frames.json'))?path.join(root,name,'frames.json'):path.join(root,'frames.json');
 const meta=JSON.parse(fs.readFileSync(metadataPath,'utf8'));
 assert.deepStrictEqual(data[name].indices,meta.sourceIndices);
 assert.deepStrictEqual(data[name].times,meta.durationMs);
 for(const url of data[name].urls)assert(fs.existsSync(path.join(root,url)));
}
const properties={},body={dataset:{}};
const context={document:{getElementById:id=>roots[id]||top[id],documentElement:{style:{setProperty:(k,v)=>properties[k]=v}},body},Image:class{},requestAnimationFrame:fn=>queue.push(fn)};
vm.runInNewContext(source,context);
const raf=now=>{assert(queue.length);queue.shift()(now)};raf(0);
let now=0;for(const name of Object.keys(data))roots[name].controls['.play'].onclick();
for(const [name,d] of Object.entries(data)){
 const c=roots[name].controls;
 assert.strictEqual(c['.player'].src,d.urls[0]);
 assert.strictEqual(c['.play'].textContent,'재생');
 const held=c['.player'].src;now+=100;raf(now);assert.strictEqual(c['.player'].src,held);
 c['.next'].onclick();assert.strictEqual(c['.player'].src,d.urls[1]);
 c['.prev'].onclick();assert.strictEqual(c['.player'].src,d.urls[0]);
 c['.prev'].onclick();assert.strictEqual(c['.player'].src,d.urls.at(-1));
 c['.seek'].oninput({target:{value:'0'}});assert.strictEqual(c['.seek'].value,0);
 c['.speed'].onchange({target:{value:'2'}});c['.play'].onclick();
 now+=250;raf(now);assert.notStrictEqual(c['.player'].src,d.urls[0]);
 assert(c['.position'].textContent.includes('원본'));
 c['.play'].onclick();
}
top.zoom.onchange({target:{value:'2'}});assert.strictEqual(properties['--zoom'],'2');
top.background.onchange({target:{value:'checker'}});assert.strictEqual(body.dataset.bg,'checker');
const result={passed:true,players:Object.keys(data),checks:['actual export script','play/pause','previous/next and wrap','seek','2x speed','source frame labels','integer zoom control','background control','referenced selected PNGs'],actualBrowserVerified:false};
fs.writeFileSync(path.join(root,'preview-behaviour-validation.json'),JSON.stringify(result,null,2));
console.log('PASS actual player script, playback, stepping, seek, speed, zoom and background');
