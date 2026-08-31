(function(){
  'use strict';
  try{
    const PATCH_LAYER_NAMES=new Set(['migration','patch','patch_package']);
    const RELEASE_LAYER_NAMES=new Set(['release','version','release_version']);
    const isPatch=n=>!!n&&(PATCH_LAYER_NAMES.has(String(n.layer||'').toLowerCase())||String(n.entityType||n.type||'').toLowerCase().includes('patch')||/^v118z/i.test(String(n.fullLabel||n.label||n.id||'')));
    const isRelease=n=>!!n&&(RELEASE_LAYER_NAMES.has(String(n.layer||'').toLowerCase())||String(n.entityType||n.type||'').toLowerCase().includes('release'));
    const isFunctional=n=>!!n&&!isPatch(n)&&!isRelease(n);
    const nodeColor=n=>{
      if(!n)return '#91a5be';
      if(typeof layerColors!=='undefined'&&layerColors[n.layer])return layerColors[n.layer];
      if(isRelease(n))return '#54d7ff';
      if(isPatch(n))return '#ff5ebc';
      return '#8bdcff';
    };
    function uniq(a){return [...new Set(a.filter(Boolean))]}
    function patchTargets(n){
      let ids=[];
      if(Array.isArray(n.targets))ids.push(...n.targets);
      if(typeof DATA!=='undefined'&&Array.isArray(DATA.edges)){
        for(const e of DATA.edges){
          if(e.a===n.id){const x=nodeMap.get(e.b);if(isFunctional(x))ids.push(x.id)}
          else if(e.b===n.id){const x=nodeMap.get(e.a);if(isFunctional(x))ids.push(x.id)}
        }
      }
      return uniq(ids).map(id=>nodeMap.get(id)).filter(Boolean);
    }
    function patchColors(n){return uniq(patchTargets(n).map(nodeColor));}

    let routeMode=false,routeNodes=new Set(),routeEdges=new Set();
    let v5LabelsVisible=true;
    const edgeKey=e=>`${e.a}→${e.b}::${e.type||''}`;
    function computeRoute(id){
      routeNodes=new Set();routeEdges=new Set();
      if(!id||typeof DATA==='undefined')return;
      routeNodes.add(id);
      const first=[];
      for(const e of DATA.edges){
        if(e.a===id||e.b===id){
          routeEdges.add(edgeKey(e));
          const other=e.a===id?e.b:e.a;
          routeNodes.add(other);first.push(other);
        }
      }
      const origin=nodeMap.get(id);
      if(isRelease(origin)){
        for(const nid of first){const n=nodeMap.get(nid);if(!isPatch(n))continue;for(const e of DATA.edges){if(e.a===nid||e.b===nid){const other=e.a===nid?e.b:e.a;const o=nodeMap.get(other);if(isFunctional(o)){routeNodes.add(other);routeEdges.add(edgeKey(e));}}}}
      }else if(isFunctional(origin)){
        for(const nid of first){const n=nodeMap.get(nid);if(!(isPatch(n)||isRelease(n)))continue;for(const e of DATA.edges){if(e.a===nid||e.b===nid){const other=e.a===nid?e.b:e.a;const o=nodeMap.get(other);if((isPatch(n)&&isRelease(o))||(isRelease(n)&&isPatch(o))){routeNodes.add(other);routeEdges.add(edgeKey(e));}}}}
      }
    }
    function setRoute(on){
      if(on&&!selected){flashRouteHint();return;}
      routeMode=!!on;
      if(routeMode)computeRoute(selected);else{routeNodes.clear();routeEdges.clear();}
      syncRouteButtons();dirty=true;
    }
    function flashRouteHint(){
      const b=document.getElementById('routeBtn');if(!b)return;const old=b.textContent;b.textContent='Сначала выберите узел';setTimeout(()=>{b.textContent=old},1300);
    }
    function syncRouteButtons(){
      for(const id of ['routeBtn','routeInfoBtn']){const b=document.getElementById(id);if(!b)continue;b.classList.toggle('on',routeMode);b.textContent=routeMode?'Скрыть маршрут':'Показать маршрут';}
    }

    const drawer=document.getElementById('drawer');
    if(drawer){
      const legend=document.createElement('div');legend.className='routeLegend';legend.innerHTML='<b>Как читать карту</b><div><span class="lg release"></span> RELEASE / VERSION</div><div><span class="lg patch"></span> PATCH PACKAGE, ободок = затронутые блоки</div><div><span class="lg module"></span> функциональный блок</div><div class="routeLegendNote">Выберите узел и включите маршрут. Всё лишнее погаснет.</div>';
      const sep=document.createElement('div');sep.className='sep';drawer.appendChild(sep);drawer.appendChild(legend);
      const routeBtn=document.createElement('button');routeBtn.id='routeBtn';routeBtn.className='ctrl routeBtn';routeBtn.textContent='Показать маршрут';routeBtn.onclick=()=>setRoute(!routeMode);drawer.appendChild(routeBtn);
    }
    const st=document.createElement('style');st.textContent=`
      .routeLegend{font-size:10px;line-height:1.55;color:#b9cbe0}.routeLegend b{display:block;color:#eef7ff;margin-bottom:4px}
      .routeLegend>div{display:flex;align-items:center;gap:7px}.routeLegendNote{display:block!important;color:#7f95ae;margin-top:5px}
      .lg{width:12px;height:12px;display:inline-block;flex:0 0 auto}.lg.release{border:2px solid #54d7ff;border-radius:50%;box-shadow:0 0 8px #54d7ff88}.lg.patch{background:#07111f;border:2px solid #ff5ebc;clip-path:polygon(25% 7%,75% 7%,100% 50%,75% 93%,25% 93%,0 50%)}.lg.module{border-radius:50%;background:#39d7b4;box-shadow:0 0 8px #39d7b488}.routeBtn{margin-top:8px;width:100%;font-weight:800}
      @media(min-width:700px){
        #info{width:min(560px,calc(100vw - 40px))!important;max-height:min(52vh,520px)!important;transition:none!important;}
        #info.v5Moved{left:0!important;bottom:auto!important;transform:none!important;}
        #info .v5DragHandle{position:sticky;top:-14px;z-index:4;margin:-14px -16px 10px;padding:7px 42px 7px 12px;background:#0b1929f2;border-bottom:1px solid #294766;color:#91a5be;font-size:10px;font-weight:800;letter-spacing:.04em;cursor:grab;user-select:none;touch-action:none}
        #info .v5DragHandle:active{cursor:grabbing;color:#eef7ff}
      }
      @media(max-width:699px){#info .v5DragHandle{display:none}}
    `;document.head.appendChild(st);

    const labelsBtn=document.getElementById('labelsBtn');
    if(labelsBtn){
      v5LabelsVisible=labelsBtn.textContent!=='Показать надписи';
      labelsBtn.classList.toggle('on',v5LabelsVisible);
      labelsBtn.onclick=e=>{v5LabelsVisible=!v5LabelsVisible;e.currentTarget.classList.toggle('on',v5LabelsVisible);e.currentTarget.textContent=v5LabelsVisible?'Скрыть надписи':'Показать надписи';dirty=true;};
    }

    const infoBox=document.getElementById('info');
    let infoDragging=false,dragDX=0,dragDY=0,dragW=0,dragH=0;
    function addInfoDragHandle(box){
      if(!box||window.innerWidth<700)return;
      const h=document.createElement('div');h.className='v5DragHandle';h.textContent='↕↔  ПЕРЕТАЩИТЬ КАРТОЧКУ';box.prepend(h);
      h.addEventListener('pointerdown',ev=>{if(ev.button!==undefined&&ev.button!==0)return;ev.preventDefault();ev.stopPropagation();const r=box.getBoundingClientRect();dragDX=ev.clientX-r.left;dragDY=ev.clientY-r.top;dragW=r.width;dragH=r.height;box.classList.add('v5Moved');box.style.left=r.left+'px';box.style.top=r.top+'px';box.style.bottom='auto';box.style.transform='none';infoDragging=true;try{h.setPointerCapture(ev.pointerId)}catch(_){}});
      h.addEventListener('dblclick',ev=>{ev.preventDefault();box.classList.remove('v5Moved');box.style.left='';box.style.top='';box.style.bottom='';box.style.transform='';});
    }
    window.addEventListener('pointermove',ev=>{if(!infoDragging||!infoBox)return;ev.preventDefault();const margin=8,minTop=66,maxX=Math.max(margin,window.innerWidth-dragW-margin),maxY=Math.max(minTop,window.innerHeight-Math.min(dragH,120)-margin);const x=Math.max(margin,Math.min(maxX,ev.clientX-dragDX)),y=Math.max(minTop,Math.min(maxY,ev.clientY-dragDY));infoBox.style.left=x+'px';infoBox.style.top=y+'px';});
    window.addEventListener('pointerup',()=>{infoDragging=false});
    window.addEventListener('resize',()=>{if(!infoBox||!infoBox.classList.contains('v5Moved'))return;const r=infoBox.getBoundingClientRect();const x=Math.max(8,Math.min(window.innerWidth-r.width-8,r.left)),y=Math.max(66,Math.min(window.innerHeight-80,r.top));infoBox.style.left=x+'px';infoBox.style.top=y+'px';});

    const originalShowInfo=showInfo;
    showInfo=function(n){
      originalShowInfo(n);
      if(routeMode)computeRoute(n.id);
      setTimeout(()=>{
        const box=document.getElementById('info');if(!box)return;
        addInfoDragHandle(box);
        if(!document.getElementById('routeInfoBtn')){const b=document.createElement('button');b.id='routeInfoBtn';b.className='ctrl';b.style.marginTop='8px';b.textContent=routeMode?'Скрыть маршрут':'Показать маршрут';b.onclick=()=>setRoute(!routeMode);box.appendChild(b);}syncRouteButtons();
      },0);
      dirty=true;
    };
    const originalCloseInfo=closeInfo;
    closeInfo=function(){originalCloseInfo();if(routeMode)setRoute(false)};window.closeInfo=closeInfo;

    function drawHex(x,y,r){ctx.beginPath();for(let i=0;i<6;i++){const a=Math.PI/3*i-Math.PI/2,xx=x+Math.cos(a)*r,yy=y+Math.sin(a)*r;i?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy)}ctx.closePath()}
    function drawPatchRing(n,p,r,alpha){
      const cols=patchColors(n);const shown=cols.slice(0,3);if(!shown.length)shown.push('#ff5ebc');
      const gap=.10,total=Math.PI*2,seg=total/shown.length;
      ctx.save();ctx.lineWidth=Math.max(1.6,r*.28);ctx.lineCap='round';ctx.globalAlpha=alpha;
      shown.forEach((c,i)=>{ctx.strokeStyle=c;ctx.shadowColor=c;ctx.shadowBlur=8;ctx.beginPath();ctx.arc(p.x,p.y,r*1.32,-Math.PI/2+i*seg+gap,-Math.PI/2+(i+1)*seg-gap);ctx.stroke()});ctx.restore();
      return cols.length;
    }
    function edgeFunctionalColor(a,b){if(isFunctional(a))return nodeColor(a);if(isFunctional(b))return nodeColor(b);return null}
    function uncertainEdge(e){const t=String(e.type||'').toLowerCase(),ev=String(e.evidence||'').toLowerCase();return e.confirmed===false||t.includes('infer')||t.includes('unknown')||ev.includes('infer')||ev.includes('unknown')}

    draw=function(){
      if(!dirty){requestAnimationFrame(draw);return}dirty=false;drawBg();
      const proj=new Map(),arr=[],drawnLabels=[];
      for(const n of DATA.nodes){if(!isVisible(n))continue;const p=screen(n);proj.set(n.id,p);arr.push({n,p})}lastProj=arr;
      ctx.lineCap='round';
      for(const e of DATA.edges){
        const a=nodeMap.get(e.a),b=nodeMap.get(e.b);if(!a||!b||!isVisible(a)||!isVisible(b))continue;const pa=proj.get(a.id),pb=proj.get(b.id);if(!pa||!pb)continue;
        const inRoute=routeMode&&routeEdges.has(edgeKey(e));const touchesSelected=selected&&(a.id===selected||b.id===selected);const focus=inRoute||(!routeMode&&touchesSelected);
        const fc=edgeFunctionalColor(a,b);const uncertain=uncertainEdge(e);
        if(fc)ctx.strokeStyle=fc;else if(isRelease(a)||isRelease(b))ctx.strokeStyle='#54d7ff';else if(isPatch(a)||isPatch(b))ctx.strokeStyle='#ff5ebc';else ctx.strokeStyle='#5f8fb8';
        if(routeMode)ctx.globalAlpha=inRoute?.96:.012;else ctx.globalAlpha=focus?.82:(e.type==='sequence'?.045:.075);
        ctx.lineWidth=inRoute?2.6:(focus?2:.65);ctx.setLineDash(uncertain?[5,5]:(e.type==='sequence'?[3,6]:[]));
        ctx.beginPath();ctx.moveTo(pa.x,pa.y);ctx.lineTo(pb.x,pb.y);ctx.stroke();
      }
      ctx.setLineDash([]);ctx.globalAlpha=1;
      arr.sort((A,B)=>A.p.z-B.p.z);
      for(const {n,p} of arr){
        const patch=isPatch(n),release=isRelease(n),hit=textMatch(n),sel=n.id===selected,onRoute=!routeMode||routeNodes.has(n.id);
        const depth=Math.max(.45,Math.min(1.7,(camDist+p.z)/camDist));let rad=patch?4.2:(release?6.8:7.2);if(n.layer==='core')rad=14;rad*=Math.max(.58,Math.min(1.55,p.p*2.9))*depth;if(hit)rad*=1.5;if(sel)rad*=1.4;
        const c=nodeColor(n),nodeAlpha=routeMode?(onRoute?1:.09):(patch?.80:.96);
        ctx.save();ctx.globalAlpha=nodeAlpha;ctx.shadowColor=c;ctx.shadowBlur=(sel||hit||onRoute&&routeMode)?18:(patch?6:11);
        if(patch){ctx.fillStyle='#07111f';ctx.strokeStyle='#ff5ebc';ctx.lineWidth=sel?2.4:1.2;drawHex(p.x,p.y,rad);ctx.fill();ctx.stroke();drawPatchRing(n,p,rad,nodeAlpha)}
        else if(release){ctx.fillStyle='#07111f';ctx.strokeStyle=c;ctx.lineWidth=sel?3:2;ctx.beginPath();ctx.arc(p.x,p.y,rad,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.globalAlpha=nodeAlpha*.75;ctx.beginPath();ctx.arc(p.x,p.y,rad*.48,0,Math.PI*2);ctx.fillStyle=c;ctx.fill()}
        else{ctx.fillStyle=c;ctx.strokeStyle='#eaf8ff';ctx.lineWidth=sel?2.4:1.2;ctx.beginPath();ctx.arc(p.x,p.y,rad,0,Math.PI*2);ctx.fill();ctx.stroke()}
        ctx.restore();
        const labelsGloballyOn=v5LabelsVisible;
        const forceRoute=routeMode&&onRoute;const showLabel=labelsGloballyOn&&(!patch||sel||hit||forceRoute||userZoom>1.45);
        if(showLabel){
          const label=n.fullLabel||n.label||(patch?'PATCH':'NODE'),font=patch?9:11;ctx.font=`700 ${font}px -apple-system,Segoe UI,Arial`;const measured=ctx.measureText(label).width,maxW=patch?230:210,tw=Math.min(maxW,measured);const tx=(measured>maxW&&label.length>12)?label.slice(0,Math.max(10,Math.floor((maxW/measured)*label.length)-1))+'…':label;const lx=p.x+rad+6,ly=p.y-rad-2,box={x:lx-3,y:ly-font,w:tw+7,h:font+6};let overlap=false;for(const b of drawnLabels){if(!(box.x+box.w<b.x||b.x+b.w<box.x||box.y+box.h<b.y||b.y+b.h<box.y)){overlap=true;break}}
          const force=sel||hit||forceRoute||n.layer==='core';if(force||!overlap){drawnLabels.push(box);ctx.globalAlpha=routeMode&&!onRoute?.08:(patch?.72:.90);ctx.fillStyle='#06101ddd';ctx.fillRect(box.x,box.y,box.w,box.h);ctx.fillStyle='#eef7ff';ctx.fillText(tx,lx,ly);ctx.globalAlpha=1}
        }
        if(patch&&sel){const count=patchColors(n).length;if(count>3){ctx.font='700 9px -apple-system,Segoe UI,Arial';ctx.fillStyle='#fff';ctx.globalAlpha=.9;ctx.fillText('+'+(count-3),p.x+rad*1.8,p.y+3);ctx.globalAlpha=1}}
      }
      requestAnimationFrame(draw);
    };
    dirty=true;requestAnimationFrame(draw);
  }catch(e){console.error('Bonifaciy V5 visual enhancement error',e)}
})();