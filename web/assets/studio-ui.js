window.StudioUI={
 async api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Sprite-Request':'1'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'요청에 실패했습니다.');return data},
 node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n},
 async dataURL(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})},
 async bitmap(url){const r=await fetch(url);if(!r.ok)throw Error('이미지를 불러오지 못했습니다.');return createImageBitmap(await r.blob())},
 link(text,url){const a=document.createElement('a');a.textContent=text;a.href=url;a.className='ui-btn';return a},
 async busy(button,work){button.disabled=true;try{await work()}catch(e){const out=document.getElementById('studioStatus');if(out)out.textContent=e.message;else alert(e.message)}finally{button.disabled=false}}
};
