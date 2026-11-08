const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),path=require('node:path');
const math=require('../web/rigging-animation-math.js');
for(let i=0;i<100;i++){
 const root={x:13,y:24},target={x:13+Math.cos(i)*i,y:24+Math.sin(i)*i},result=math.solveTwoBone(root,target,20,25,i%2?1:-1);
 assert(Math.abs(Math.hypot(result.mid.x-root.x,result.mid.y-root.y)-20)<1e-8);
 assert(Math.abs(Math.hypot(result.end.x-result.mid.x,result.end.y-result.mid.y)-25)<1e-8);
 const raw=Math.hypot(target.x-root.x,target.y-root.y);if(raw>5.001&&raw<44.999)assert(Math.hypot(result.end.x-target.x,result.end.y-target.y)<1e-8);
}
assert.equal(math.solveTwoBone({x:0,y:0},{x:1,y:1},0,5),null);
const a=math.solveTwoBone({x:0,y:0},{x:20,y:0},20,20,1),b=math.solveTwoBone({x:0,y:0},{x:20,y:0},20,20,-1);assert(a.mid.y>0&&b.mid.y<0);
const root=path.resolve(__dirname,'..');
const fixtures=JSON.parse(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import rigging_animation as animation,json
cases=[]
for loop in [True,False]:
 for easing in ['linear','smooth','hold']:
  clip={'frames':48,'loop':loop,'easing':easing,'keys':[{'frame':4,'pose':{'head':{'dx':5,'angle':179}}},{'frame':24,'pose':{'head':{'dy':12,'angle':-179}}}]}
  for frame in [-1,0,4,9,14,23.5,24,36,47.5,48,50]:cases.append({'clip':clip,'frame':frame,'expected':animation.sample(clip,frame)})
print(json.dumps(cases))
`],{cwd:root,encoding:'utf8'}));
for(const test of fixtures){const value=math.sample(test.clip,test.frame);assert.deepEqual(Object.keys(value).sort(),Object.keys(test.expected).sort());for(const bone of Object.keys(value))for(const field of ['dx','dy','angle'])assert(Math.abs(value[bone][field]-test.expected[bone][field])<1e-9)}
console.log('IK geometry and 66 Python/JS interpolation comparisons passed.');
