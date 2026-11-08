/* Local-only pixel recipe. The server owns model paths and final grid conversion. */
(()=>{
 const $=id=>document.getElementById(id),isPixel=()=>$('model').value==='pixel-art-xl',baseSize=()=>Number($('pixelSize').value)===64?1024:Number($('pixelSize').value)*8;
 window.applyPixelRecipe=()=>{
  window.restoreImageLook?.({});window.restoreImageStyle?.({});window.restoreImagePose?.({});
  $('mode').value=$('pixelInput').value;$('model').value='pixel-art-xl';
  if($('model').value!=='pixel-art-xl')throw Error('픽셀 전용 세팅을 불러오지 못했어요. 새로고침해 주세요.');
  $('model').dispatchEvent(new CustomEvent('change',{detail:{assetSetup:true}}));
  $('preset').value=$('pixelSubject').value;$('faceDetail').checked=$('hiresFix').checked=false;$('denoise').value=.7;
  $('size').value=baseSize()+'x'+baseSize();
  modeChanged();
 };
 window.imagePixelPayload=()=>isPixel()?{pixelSize:Number($('pixelSize').value),pixelColors:Number($('pixelColors').value)}:{};
 window.restorePixelSettings=s=>{if(s.model!=='pixel-art-xl')return;$('pixelSize').value=String(s.pixelSize||128);$('pixelColors').value=String(s.pixelColors??32);$('pixelSubject').value=s.preset==='illustration'?'illustration':'sprite';$('pixelInput').value=s.mode==='reference'?'reference':'text';$('mode').value=$('pixelInput').value;$('size').value=baseSize()+'x'+baseSize();modeChanged()};
 function sync(){const pixel=isPixel();$('pixelControls').hidden=!pixel;document.body.classList.toggle('pixel-recipe',pixel);if(!pixel)return;
  const model=models.find(m=>m.id==='pixel-art-xl');$('pixelReady').textContent=model?.ready?'로컬 모델 설치됨 · 정지 이미지 초안 · 실제 생성 품질 검증은 별도입니다.':'픽셀 전용 모델 준비 중 · 설치가 끝나면 페이지를 새로고침하세요. 아직 생성할 수 없습니다.';
  $('size').disabled=true;
 }
 $('pixelSize').onchange=()=>{$('size').value=baseSize()+'x'+baseSize();$('size').dispatchEvent(new Event('change'))};
 $('pixelColors').onchange=()=>{$('count').dispatchEvent(new Event('change'))};
 $('pixelSubject').onchange=()=>{if(isPixel())$('preset').value=$('pixelSubject').value};
 $('pixelInput').onchange=()=>{if(!isPixel())return;$('mode').value=$('pixelInput').value;$('mode').dispatchEvent(new Event('change'))};
 $('model').addEventListener('change',()=>{if(!isPixel())$('size').disabled=false;sync()});
 window.addEventListener('image-models-ready',sync);sync();
})();
