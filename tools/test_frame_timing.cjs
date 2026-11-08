/* Exercise the actual editor playback functions without a browser renderer. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/assets/frame-editor.js'),'utf8');
const funcs=['stop','playRange'].map(name=>source.split('\n').find(line=>line.startsWith(`function ${name}(`))).join('\n');
const calls=[],cleared=[],drawn=[];let seq=0;
const c=vm.createContext({doc:{fps:20,frames:[{durationMs:40},{durationMs:110}]},playing:null,index:0,playIndex:0,
 $:()=>({textContent:''}),draw(){drawn.push(c.playing?c.playIndex:c.index)},
 setTimeout(fn,ms){calls.push({fn,ms,id:++seq});return seq},clearTimeout(id){cleared.push(id)}});
vm.runInContext(funcs,c);c.playRange({start:0,end:1});assert.equal(calls.at(-1).ms,40);assert.deepEqual(drawn,[0]);
calls.at(-1).fn();assert.equal(calls.at(-1).ms,110);assert.deepEqual(drawn,[0,1]);
calls.at(-1).fn();assert.equal(calls.at(-1).ms,40);assert.deepEqual(drawn,[0,1,0]);
c.stop();assert.equal(c.playing,null);assert.equal(cleared.at(-1),3);
c.doc.frames=[{},{}];c.playRange({start:0,end:1});assert.equal(calls.at(-1).ms,50);c.stop();
console.log('PASS actual frame editor: per-frame timing, wrapping, stop, FPS fallback');
