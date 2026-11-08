(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RigAnimationMath=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function solveTwoBone(root, target, l1, l2, bend=1){
  if(l1<1e-6||l2<1e-6)return null;
  const dx=target.x-root.x,dy=target.y-root.y,raw=Math.hypot(dx,dy),min=Math.abs(l1-l2)+1e-5,max=l1+l2-1e-5,d=Math.max(min,Math.min(max,raw)),heading=raw<1e-8?0:Math.atan2(dy,dx),offset=Math.acos(Math.max(-1,Math.min(1,(l1*l1+d*d-l2*l2)/(2*l1*d))));
  const angle=heading+(bend>=0?1:-1)*offset,mid={x:root.x+l1*Math.cos(angle),y:root.y+l1*Math.sin(angle)},end={x:root.x+d*Math.cos(heading),y:root.y+d*Math.sin(heading)};
  return{mid,end,clamped:Math.abs(d-raw)>1e-4};
 }
 function sample(clip,frame){
  const keys=clip.keys;if(!keys.length)return{};
  frame=clip.loop?((frame%clip.frames)+clip.frames)%clip.frames:Math.max(0,Math.min(clip.frames-1,frame));
  let a=keys[0],b=a,fa=a.frame,fb=fa;
  if(frame<keys[0].frame){if(clip.loop){a=keys.at(-1);b=keys[0];fa=a.frame-clip.frames;fb=b.frame}}
  else if(frame>=keys.at(-1).frame){a=b=keys.at(-1);fa=fb=a.frame;if(clip.loop){b=keys[0];fb=b.frame+clip.frames}}
  else for(let i=0;i<keys.length-1;i++)if(keys[i].frame<=frame&&frame<keys[i+1].frame){a=keys[i];b=keys[i+1];fa=a.frame;fb=b.frame;break}
  let t=fa===fb?0:(frame-fa)/(fb-fa);t=clip.easing==='hold'?0:clip.easing==='smooth'?t*t*(3-2*t):t;
  const pose={};for(const name of new Set([...Object.keys(a.pose),...Object.keys(b.pose)])){const av=a.pose[name]||{},bv=b.pose[name]||{},aa=av.angle||0,ba=bv.angle||0;pose[name]={dx:(av.dx||0)+((bv.dx||0)-(av.dx||0))*t,dy:(av.dy||0)+((bv.dy||0)-(av.dy||0))*t,angle:aa+(((ba-aa+180)%360+360)%360-180)*t}}
  return pose;
 }
 return{solveTwoBone,sample};
});
