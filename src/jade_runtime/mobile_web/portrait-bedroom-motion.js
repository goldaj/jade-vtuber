/* Portrait bedroom only. Five independent, masked effects sourced from the
 * actual painted AVIF. Never move or warp the room image or the avatar.
 * Calibration: 864x1536 portrait art; reference fullscreen capture 691x1525
 * (center-cropped). Shapes are deliberately inset from fixed architectural edges.
 * If the artwork changes aspect or cannot be sampled, leave it static. */
"use strict";
(() => {
  const W = 864, H = 1536, FRAME_MS = 1000 / 24;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const smooth = (a,b,v) => {const t=clamp((v-a)/(b-a),0,1);return t*t*(3-2*t);};
  const point = ([x,y]) => [W/2+(x-345.5)*H/1525,y*H/1525];
  const poly = points => points.map(point);
  // Each polygon is wholly inside one material/surface. Never span a beam,
  // the curtain rail, a mullion, a window ledge, or the furniture.
  const curtainRegions = [
    poly([[446,330],[460,324],[495,309],[515,305],[514,383],[504,436],[486,474],[446,456],[432,420]]),
    poly([[447,739],[489,746],[500,850],[493,876],[470,883],[443,879],[436,853]])
  ];
  const blossomRegions = [
    poly([[548,370],[563,337],[595,310],[599,348]]),
    poly([[613,300],[660,279],[660,323],[613,342]]),
    poly([[548,384],[599,361],[599,393],[548,410]]),
    poly([[613,353],[661,334],[661,368],[613,388]]),
    poly([[560,437],[650,412],[650,506],[560,513]])
  ];
  const lightRegions = [
    poly([[0,4],[277,4],[246,90],[0,100]]),
    poly([[493,4],[690,4],[690,93],[551,159],[476,128],[404,99]]),
    poly([[248,151],[361,128],[477,186],[382,266],[185,263]]),
    poly([[0,310],[111,331],[111,413],[0,435]])
  ];
  const birdRegion = poly([[560,491],[650,475],[650,544],[560,572]]);
  function inside(p,x,y) {
    let yes=false;
    for(let i=0,j=p.length-1;i<p.length;j=i++){
      const [xi,yi]=p[i],[xj,yj]=p[j];
      if((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) yes=!yes;
    }
    return yes;
  }
  function edgeDistance(p,x,y) {
    let best=Infinity;
    for(let i=0,j=p.length-1;i<p.length;j=i++){
      const [a,b]=p[j],[c,d]=p[i],dx=c-a,dy=d-b;
      const t=clamp(((x-a)*dx+(y-b)*dy)/(dx*dx+dy*dy||1),0,1);
      best=Math.min(best,Math.hypot(x-a-t*dx,y-b-t*dy));
    }
    return best;
  }
  function maskAlpha(p,x,y,feather=8) {
    return inside(p,x,y)?smooth(0,feather,edgeDistance(p,x,y)):0;
  }
  function windAt(t) {
    return (.78+.22*Math.sin(.17*t+.8))*(.58*Math.sin(.43*t+.4)+
      .29*Math.sin(.87*t+1.3)+.13*Math.sin(1.48*t+2.1));
  }
  function curtainOffset(y,t,wind=windAt(t)) {
    // Folds flutter more toward the bottom; the attachment stays fixed.
    const pin=smooth(308,445,y);
    return pin===0?0:pin*(6.5*wind+2.1*Math.sin(1.48*t-y*.018));
  }
  function lightAlpha(r,g,b) {
    return smooth(144,187,g)*smooth(193,236,r)*smooth(7,24,g-b)*
      (1-smooth(82,105,r-g));
  }
  function branchAlpha(r,g,b) {
    // Exclude blue sky. The narrow per-pane masks exclude frames and clouds.
    const sky=Math.max(smooth(14,39,b-r)*smooth(6,22,g-r),
      smooth(12,30,b-g)*smooth(8,32,b-r));
    return 1-sky;
  }
  function fabricAlpha(r,g,b) {
    return smooth(94,134,b)*smooth(100,146,g)*(1-smooth(90,120,r-b));
  }
  function shouldRun(ready,bedroom,visible,hidden,reduced) {
    return Boolean(ready&&bedroom&&visible&&!hidden&&!reduced);
  }
  function birdProgress(t) {
    // Occasional small flock, not a constant procession across the window.
    const phase=t%31;
    return phase>=6&&phase<=11.5?(phase-6)/5.5:-1;
  }
  if(typeof module!=="undefined"&&module.exports){
    module.exports={W,H,curtainRegions,blossomRegions,lightRegions,birdRegion,
      inside,maskAlpha,windAt,curtainOffset,lightAlpha,branchAlpha,fabricAlpha,shouldRun,birdProgress};
    return;
  }
  const room=document.querySelector(".room");
  const backdrop=document.getElementById("portrait-bedroom");
  const canvas=document.getElementById("portrait-bedroom-motion");
  if(!room||!backdrop||!canvas)return;
  const preference=matchMedia("(prefers-reduced-motion: reduce)");
  const output=canvas.getContext("2d");
  if(!output)return;
  let prepared=null,failed=false,visible=true,frame=null,elapsed=0,last=null,lastPaint=-Infinity;
  function surface(w,h) {
    const c=document.createElement("canvas");c.width=w;c.height=h;return c;
  }
  function region(source,p,feather,material=null) {
    const x=Math.max(0,Math.floor(Math.min(...p.map(q=>q[0]))));
    const y=Math.max(0,Math.floor(Math.min(...p.map(q=>q[1]))));
    const w=Math.min(W-x,Math.ceil(Math.max(...p.map(q=>q[0])))-x+1);
    const h=Math.min(H-y,Math.ceil(Math.max(...p.map(q=>q[1])))-y+1);
    const data=source.getContext("2d").getImageData(x,y,w,h);
    const mask=surface(w,h), mc=mask.getContext("2d"), mi=mc.createImageData(w,h);
    const coverage=new Float32Array(w*h);
    for(let j=0;j<h;j++)for(let i=0;i<w;i++){
      const n=j*w+i,k=n*4;
      let a=maskAlpha(p,x+i+.5,y+j+.5,feather);
      if(material)a*=material(data.data[k],data.data[k+1],data.data[k+2]);
      coverage[n]=a;mi.data[k+3]=Math.round(a*255);
    }
    mc.putImageData(mi,0,0);
    return {x,y,w,h,data,mask,coverage,work:surface(w,h)};
  }
  // Separate the painted feature from its local background once. Fill only
  // the selected feature pixels using nearest same-pane/ceiling base colors.
  // No image warping or interpolation of neighboring fixed room elements.
  function separate(source,p,classify,feather) {
    const q=region(source,p,feather);
    const {w,h,data,coverage}=q,n=w*h,rgba=data.data;
    const alpha=new Float32Array(n),nearest=new Int32Array(n),queue=new Int32Array(n);
    nearest.fill(-1);
    let head=0,tail=0,features=0;
    for(let i=0;i<n;i++){
      if(coverage[i]<=.02)continue;
      const k=i*4;
      const a=classify(rgba[k],rgba[k+1],rgba[k+2]);
      alpha[i]=a;
      if(a<.12){nearest[i]=i;queue[tail++]=i;}
      if(a>.65)features++;
    }
    // A mismatched asset or mask with no recoverable background is skipped.
    if(tail<n*.035||features<12||features>tail*2.7)return null;
    function visit(i,seed){
      if(i<0||i>=n||nearest[i]!==-1||coverage[i]<=.02)return;
      nearest[i]=seed;queue[tail++]=i;
    }
    while(head<tail){
      const i=queue[head++],seed=nearest[i],col=i%w;
      if(col>0)visit(i-1,seed);
      if(col<w-1)visit(i+1,seed);
      visit(i-w,seed);visit(i+w,seed);
    }
    const clean=surface(w,h),fg=surface(w,h);
    const bc=clean.getContext("2d"),fc=fg.getContext("2d");
    const bi=bc.createImageData(w,h),fi=fc.createImageData(w,h);
    bi.data.set(rgba);
    for(let i=0;i<n;i++){
      const k=i*4,a=alpha[i],seed=nearest[i];
      if(seed<0||a<.02)continue;
      for(let c=0;c<3;c++){
        bi.data[k+c]=Math.round(rgba[k+c]*(1-a)+rgba[seed*4+c]*a);
        fi.data[k+c]=rgba[k+c];
      }
      fi.data[k+3]=Math.round(a*255);
    }
    bc.putImageData(bi,0,0);fc.putImageData(fi,0,0);
    return {...q,clean,fg};
  }
  function prepare() {
    if(prepared||failed||!backdrop.complete||!backdrop.naturalWidth)return;
    if(backdrop.naturalWidth!==W||backdrop.naturalHeight!==H){failed=true;return;}
    try{
      const source=surface(W,H);
      source.getContext("2d",{willReadFrequently:true}).drawImage(backdrop,0,0,W,H);
      prepared={source,
        curtains:curtainRegions.map(p=>region(source,p,10,fabricAlpha)),
        lights:lightRegions.map(p=>separate(source,p,lightAlpha,12)).filter(Boolean),
        branches:blossomRegions.map(p=>separate(source,p,branchAlpha,7)).filter(Boolean)};
    }catch(error){
      failed=true;console.warn("Portrait bedroom motion unavailable:",error);
    }
  }
  function composite(q,draw) {
    const c=q.work.getContext("2d");
    c.globalCompositeOperation="source-over";c.globalAlpha=1;
    c.clearRect(0,0,q.w,q.h);draw(c);
    c.globalCompositeOperation="destination-in";c.globalAlpha=1;
    c.drawImage(q.mask,0,0);c.globalCompositeOperation="source-over";
    output.drawImage(q.work,q.x,q.y);
  }
  function paintCurtain(q,t,wind) {
    composite(q,c=>{
      // Small strips sample only the cloth interior; soft mask hides edges.
      // Never sample or translate the whole backdrop or its silhouette.
      const pad=10;
      for(let j=0;j<q.h;j+=4){
        const dy=Math.min(4,q.h-j),dx=curtainOffset(q.y+j,t,wind);
        const sx=clamp(q.x-dx,0,W-q.w);
        c.drawImage(prepared.source,sx,q.y+j,q.w,dy,0,j,q.w,dy);
      }
      // A faint changing fold highlight is contained by the same fabric mask.
      c.globalCompositeOperation="source-atop";
      c.fillStyle="rgba(255,231,211,"+(.025+.025*(wind+1)/2)+")";
      c.fillRect(pad,0,Math.max(0,q.w-2*pad),q.h);
      c.globalCompositeOperation="source-over";
    });
  }
  function paintFeature(q,dx,dy,opacity) {
    composite(q,c=>{
      c.drawImage(q.clean,0,0);
      c.globalAlpha=opacity;c.drawImage(q.fg,dx,dy);c.globalAlpha=1;
    });
  }
  // Fixed, deterministic particles: no object allocation per frame and no
  // reset/teleport while visible. Interior dust is behind the avatar.
  const dust=Array.from({length:18},(_,i)=>({
    x:point([170+(i*97%470),0])[0],
    y:point([0,290+(i*131%640)])[1],
    radius:.8+(i*13%17)/10,phase:i*2.39996
  }));
  function paintDust(t,wind) {
    for(const d of dust){
      const x=d.x+18*Math.sin(.19*t+d.phase)+7*wind;
      const y=d.y+23*Math.sin(.13*t+d.phase*.73);
      const a=.12+.56*Math.pow(.5+.5*Math.sin(.62*t+d.phase),2);
      output.beginPath();output.fillStyle="rgba(255,244,202,"+a*.23+")";
      output.arc(x,y,d.radius*2.1,0,Math.PI*2);output.fill();
      output.beginPath();output.fillStyle="rgba(255,249,221,"+a+")";
      output.arc(x,y,d.radius,0,Math.PI*2);output.fill();
    }
  }
  function paintBirds(t) {
    const p=birdProgress(t);
    if(p<0)return;
    output.save();output.beginPath();
    birdRegion.forEach(([x,y],i)=>i?output.lineTo(x,y):output.moveTo(x,y));
    output.closePath();output.clip();
    output.strokeStyle="rgba(48,73,81,.82)";output.lineWidth=1.4;output.lineCap="round";
    const start=point([545,531]),end=point([670,502]);
    for(let i=0;i<3;i++){
      const x=start[0]+(end[0]-start[0])*p-i*12;
      const y=start[1]+(end[1]-start[1])*p+7*Math.sin(i*2)+3*Math.sin(t*1.5+i);
      const wing=2.8+2.1*Math.sin(t*11+i*1.5),span=4.5-i*.6;
      output.beginPath();output.moveTo(x-span,y-wing);
      output.quadraticCurveTo(x-span*.5,y-wing*.25,x,y);
      output.quadraticCurveTo(x+span*.5,y-wing*.25,x+span,y-wing);
      output.stroke();
    }
    output.restore();
  }
  function render(t) {
    output.clearRect(0,0,W,H);
    const wind=windAt(t);
    prepared.curtains.forEach(q=>paintCurtain(q,t,wind));
    prepared.lights.forEach((q,i)=>paintFeature(q,6.5*wind+2*Math.sin(t*.31+i),
      3.8*wind+1.3*Math.sin(t*.26+i),.91+.09*Math.sin(t*.48+i)));
    prepared.branches.forEach((q,i)=>paintFeature(q,4.6*wind+1.1*Math.sin(t*.94+i*.23),
      2.3*wind+1.1*Math.sin(t*.73+i*.29),1));
    paintBirds(t);paintDust(t,wind);
  }
  function tick(now) {
    frame=null;
    if(last!==null)elapsed+=Math.min(100,Math.max(0,now-last));
    last=now;
    if(now-lastPaint>=FRAME_MS-.5){
      try{render(elapsed/1000);lastPaint=now;}
      catch(error){failed=true;stop();console.warn("Portrait motion stopped:",error);return;}
    }
    frame=requestAnimationFrame(tick);
  }
  function stop() {
    if(frame!==null)cancelAnimationFrame(frame);
    frame=null;last=null;lastPaint=-Infinity;canvas.hidden=true;
  }
  function sync() {
    const running=shouldRun(room.dataset.seatedReady==="true",room.dataset.room==="bedroom",
      visible,document.hidden,preference.matches);
    if(!running||failed){stop();return;}
    prepare();
    if(!prepared){stop();return;}
    canvas.hidden=false;
    if(frame===null)frame=requestAnimationFrame(tick);
  }
  room.addEventListener("jade-room-changed",sync);
  room.addEventListener("jade-seated-ready",sync);
  backdrop.addEventListener("load",sync);
  document.addEventListener("visibilitychange",sync);
  if(preference.addEventListener)preference.addEventListener("change",sync);
  else preference.addListener(sync);
  if(typeof IntersectionObserver==="function"){
    new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync();}).observe(room);
  }
  sync();
})();
