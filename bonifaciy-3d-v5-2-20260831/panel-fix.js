(function(){
'use strict';
try{
  const style=document.createElement('style');
  style.textContent=`
    @media(min-width:700px){
      #info.v52Moved{position:fixed!important;left:var(--v52-left)!important;top:var(--v52-top)!important;right:auto!important;bottom:auto!important;transform:none!important;margin:0!important;}
      #info .v5DragHandle{padding-right:62px!important;z-index:20!important;}
      #info .v52Close{position:absolute!important;top:5px!important;right:7px!important;width:30px!important;height:30px!important;display:grid!important;place-items:center!important;padding:0!important;margin:0!important;border:1px solid #365777!important;border-radius:8px!important;background:#07111ff2!important;color:#dcecff!important;font:800 20px/1 -apple-system,Segoe UI,Arial!important;cursor:pointer!important;z-index:50!important;pointer-events:auto!important;user-select:none!important;box-shadow:0 0 0 1px #06101d88!important;}
      #info .v52Close:hover{background:#10243a!important;color:#fff!important;border-color:#5b83a8!important;}
    }
    @media(max-width:699px){#info .v52Close{display:none!important;}}
  `;
  document.head.appendChild(style);

  let drag=null;
  const margin=8;
  function clearPosition(box){
    if(!box)return;
    box.classList.remove('v5Moved','v52Moved');
    box.style.removeProperty('--v52-left');box.style.removeProperty('--v52-top');
    box.style.left='';box.style.top='';box.style.right='';box.style.bottom='';box.style.transform='';box.style.margin='';
  }
  function closePanel(ev){
    if(ev){ev.preventDefault();ev.stopPropagation();if(ev.stopImmediatePropagation)ev.stopImmediatePropagation();}
    drag=null;
    const box=document.getElementById('info');
    clearPosition(box);
    try{if(typeof window.closeInfo==='function')window.closeInfo();else if(typeof closeInfo==='function')closeInfo();else if(box){box.classList.remove('show','on','open');box.style.display='none';}}catch(_){if(box){box.classList.remove('show','on','open');box.style.display='none';}}
  }
  function clamp(x,y,w,h){
    const maxX=Math.max(margin,window.innerWidth-w-margin);
    const maxY=Math.max(margin,window.innerHeight-h-margin);
    return [Math.max(margin,Math.min(maxX,x)),Math.max(margin,Math.min(maxY,y))];
  }
  function startDrag(ev,box,handle){
    if(window.innerWidth<700)return;
    if(ev.button!==undefined&&ev.button!==0)return;
    if(ev.target&&ev.target.closest&&ev.target.closest('.v52Close'))return;
    ev.preventDefault();ev.stopImmediatePropagation();
    const r=box.getBoundingClientRect();
    box.classList.remove('v5Moved');box.classList.add('v52Moved');
    box.style.right='auto';box.style.bottom='auto';box.style.transform='none';box.style.margin='0';
    box.style.setProperty('--v52-left',r.left+'px');box.style.setProperty('--v52-top',r.top+'px');
    drag={box,handle,pointerId:ev.pointerId,dx:ev.clientX-r.left,dy:ev.clientY-r.top,w:r.width,h:r.height};
    try{handle.setPointerCapture(ev.pointerId)}catch(_){}
  }
  window.addEventListener('pointermove',ev=>{
    if(!drag||ev.pointerId!==drag.pointerId)return;
    ev.preventDefault();
    const p=clamp(ev.clientX-drag.dx,ev.clientY-drag.dy,drag.w,drag.h);
    drag.box.style.setProperty('--v52-left',p[0]+'px');drag.box.style.setProperty('--v52-top',p[1]+'px');
  },true);
  window.addEventListener('pointerup',ev=>{
    if(!drag||ev.pointerId!==drag.pointerId)return;
    try{drag.handle.releasePointerCapture(ev.pointerId)}catch(_){}
    drag=null;
  },true);
  window.addEventListener('pointercancel',()=>{drag=null},true);
  window.addEventListener('resize',()=>{
    const box=document.getElementById('info');if(!box||!box.classList.contains('v52Moved'))return;
    const r=box.getBoundingClientRect();const p=clamp(r.left,r.top,r.width,r.height);
    box.style.setProperty('--v52-left',p[0]+'px');box.style.setProperty('--v52-top',p[1]+'px');
  });

  function setup(box){
    if(!box||window.innerWidth<700)return;
    let close=box.querySelector('.v52Close');
    if(!close){close=document.createElement('button');close.type='button';close.className='v52Close';close.setAttribute('aria-label','Закрыть карточку');close.title='Закрыть';close.textContent='×';box.appendChild(close);}
    close.onpointerdown=ev=>{ev.preventDefault();ev.stopPropagation();ev.stopImmediatePropagation();};
    close.onclick=closePanel;
    const h=box.querySelector('.v5DragHandle');
    if(h&&!h.dataset.v52){
      h.dataset.v52='1';
      h.addEventListener('pointerdown',ev=>startDrag(ev,box,h),true);
      h.addEventListener('dblclick',ev=>{ev.preventDefault();ev.stopImmediatePropagation();clearPosition(box);},true);
    }
  }

  const priorShowInfo=showInfo;
  showInfo=function(n){priorShowInfo(n);setTimeout(()=>setup(document.getElementById('info')),0);};
  window.showInfo=showInfo;
  setup(document.getElementById('info'));
}catch(e){console.error('Bonifaciy V5.2 panel fix error',e)}
})();