/* Portrait bedroom only. Five independent, masked effects sourced from the
 * actual painted AVIF. Never move or warp the room image or the avatar.
 * Calibration: 864x1536 portrait art; reference fullscreen capture 691x1525
 * (center-cropped). Shapes are deliberately inset from fixed architectural edges.
 * If the artwork changes aspect or cannot be sampled, leave it static. */
"use strict";
(() => {
  const W = 864, H = 1536, FRAME_MS = 1000 / 24;
  const AMPLITUDE = Object.freeze({curtain:18, flutter:5, lightX:21, lightY:12, branchX:10, branchY:5});
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const smooth = (a,b,v) => {const t=clamp((v-a)/(b-a),0,1);return t*t*(3-2*t);};
  const point = ([x,y]) => [W/2+(x-345.5)*H/1525,y*H/1525];
  const poly = points => points.map(point);
  // Each polygon is wholly inside one material/surface. Never span a beam,
  // the curtain rail, a mullion, a window ledge, or the furniture.
  const curtainRegions = [
    poly([[441,339],[460,324],[495,309],[515,305],[516,391],[510,455],[501,489],[468,487],[432,443]]),
    poly([[440,754],[487,748],[498,819],[500,866],[492,880],[468,884],[439,875],[434,851]])
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
    const pin=smooth(308,410,y);
    return pin===0?0:pin*(AMPLITUDE.curtain*wind+AMPLITUDE.flutter*Math.sin(1.32*t-y*.018));
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
  function shouldRun(ready,bedroom,visible,hidden,enabled) {
    return Boolean(ready&&bedroom&&visible&&!hidden&&enabled);
  }
  function birdProgress(t) {
    // Occasional small flock, not a constant procession across the window.
    const phase=t%19;
    return phase>=1.5&&phase<=6.5?(phase-1.5)/5:-1;
  }
  if(typeof module!=="undefined"&&module.exports){
    module.exports={W,H,curtainRegions,blossomRegions,lightRegions,birdRegion,
      inside,maskAlpha,windAt,curtainOffset,lightAlpha,branchAlpha,fabricAlpha,shouldRun,birdProgress,AMPLITUDE};
    return;
  }
  const room=document.querySelector(".room");
  const backdrop=document.getElementById("portrait-bedroom");
  const canvas=document.getElementById("portrait-bedroom-motion");
  if(!room||!backdrop||!canvas)return;
  const preference=matchMedia("(prefers-reduced-motion: reduce)");
  // Owner explicitly enables this decorative scene. OS reduced motion uses
  // a gentler preset instead of silently disabling all five effects.
  const toggle=document.getElementById("portrait-motion-enabled");
  const status=document.getElementById("portrait-motion-status");
  if(toggle)toggle.checked=window.JadePreferences?.get("portraitMotionEnabled",true)??true;
  function report(state,message="") {
    room.dataset.portraitMotion=state;
    if(status){
      const problem=state==="unavailable"||state==="partial";
      status.textContent=problem?message:"";
      status.hidden=!problem;
    }
  }
  const output=canvas.getContext("2d");
  toggle?.addEventListener("change",()=>{
    window.JadePreferences?.set("portraitMotionEnabled",toggle.checked);
    if(output)sync();
  });
  if(!output){report("unavailable","Animations indisponibles sur ce navigateur.");return;}
  let prepared=null,visible=true,frame=null,elapsed=0,last=null,lastPaint=-Infinity;
  const disabledEffects=new Set();
  function safeEffect(name,fn) {
    if(disabledEffects.has(name))return;
    try{fn();}catch(error){
      disabledEffects.add(name);
      console.warn("Portrait bedroom effect failed:",name,error);
      report("partial","Animations actives, effet indisponible : "+name+".");
    }
  }
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
    const texture=surface(w,h),tc=texture.getContext("2d");
    tc.putImageData(data,0,0);
    tc.globalCompositeOperation="destination-in";tc.drawImage(mask,0,0);
    tc.globalCompositeOperation="source-over";
    return {x,y,w,h,data,mask,coverage,texture,work:surface(w,h)};
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
    if(prepared||!backdrop.complete||!backdrop.naturalWidth)return;
    // Particles and birds do not depend on image segmentation. Even if
    // pixel sampling fails, keep the other effects visibly running.
    prepared={curtains:[],lights:[],branches:[],pixelFallback:false};
    if(Math.abs(backdrop.naturalWidth/backdrop.naturalHeight-W/H)>.004){
      prepared.pixelFallback=true;return;
    }
    try{
      const source=surface(W,H);
      source.getContext("2d",{willReadFrequently:true}).drawImage(backdrop,0,0,W,H);
      const collect=(list,name,fn)=>list.map((p,i)=>{
        try{return fn(p);}catch(error){console.warn("Portrait mask unavailable:",name,i,error);return null;}
      }).filter(Boolean);
      prepared.curtains=collect(curtainRegions,"rideau",p=>region(source,p,9,fabricAlpha));
      // Never discard a whole animation when extraction finds too little sky
      // or wall. A material-only mask supports a safe luminous fallback.
      prepared.lights=collect(lightRegions,"lumière",p=>separate(source,p,lightAlpha,10)||
        region(source,p,10,lightAlpha));
      prepared.branches=collect(blossomRegions,"branches",p=>separate(source,p,branchAlpha,6)||
        region(source,p,6,branchAlpha));
    }catch(error){
      prepared.pixelFallback=true;console.warn("Portrait pixel extraction unavailable:",error);
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
      // Both the source and destination are masked. Translating a strip
      // cannot pull in pixels of the wall, window frame or furniture.
      c.drawImage(q.texture,0,0);
      for(let j=0;j<q.h;j+=4){
        const dy=Math.min(4,q.h-j),dx=curtainOffset(q.y+j,t,wind);
        c.drawImage(q.texture,0,j,q.w,dy,dx,j,q.w,dy);
      }
      c.globalCompositeOperation="source-atop";
      const shade=.07+.11*(.5+.5*Math.sin(t*.9+q.y*.01));
      c.fillStyle="rgba(255,229,205,"+shade+")";
      c.fillRect(0,0,q.w,q.h);
      c.globalCompositeOperation="source-over";
    });
  }
  function paintFeature(q,dx,dy,opacity,glow) {
    composite(q,c=>{
      if(q.clean&&q.fg){
        c.drawImage(q.clean,0,0);
        c.globalAlpha=opacity;c.drawImage(q.fg,dx,dy);c.globalAlpha=1;
      }else{
        // The fallback only moves isolated texture, never the source plane.
        c.globalAlpha=.72;c.drawImage(q.texture,dx,dy);c.globalAlpha=1;
      }
      if(glow>0){
        c.globalCompositeOperation="source-atop";
        c.fillStyle="rgba(255,225,177,"+glow+")";
        c.fillRect(0,0,q.w,q.h);
        c.globalCompositeOperation="source-over";
      }
    });
  }
  function paintAmbientLight(t,wind) {
    // Small, soft pools of light on wall/ceiling only. Independent of pixel
    // extraction: the visible light pulses even when the motif mask is empty.
    for(let i=0;i<lightRegions.length;i++){
      const p=lightRegions[i],center=p.reduce((a,b)=>[a[0]+b[0]/p.length,a[1]+b[1]/p.length],[0,0]);
      const x=center[0]+26*wind+9*Math.sin(t*.51+i);
      const y=center[1]+13*wind;
      output.save();output.beginPath();
      p.forEach(([px,py],j)=>j?output.lineTo(px,py):output.moveTo(px,py));
      output.closePath();output.clip();
      const g=output.createRadialGradient(x,y,0,x,y,65+i*8);
      const a=.05+.14*(.5+.5*Math.sin(t*.83+i*.9));
      g.addColorStop(0,"rgba(255,225,154,"+a+")");g.addColorStop(1,"rgba(255,225,154,0)");
      output.fillStyle=g;output.fillRect(0,0,W,H);output.restore();
    }
  }
  // Fixed, deterministic particles: no object allocation per frame and no
  // reset/teleport while visible. Interior dust is behind the avatar.
  const dust=Array.from({length:28},(_,i)=>({
    x:point([25+(i*97%635),0])[0],
    // Keep many particles in the unoccluded upper part of the scene.
    y:point([0,i<18?75+(i*131%285):365+(i*131%520)])[1],
    radius:1.3+(i*13%21)/10,phase:i*2.39996
  }));
  function paintDust(t,wind) {
    for(const d of dust){
      const x=d.x+34*Math.sin(.27*t+d.phase)+14*wind;
      const y=d.y+40*Math.sin(.22*t+d.phase*.73);
      const a=.25+.65*Math.pow(.5+.5*Math.sin(.68*t+d.phase),2);
      output.beginPath();output.fillStyle="rgba(255,244,202,"+a*.34+")";
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
    output.strokeStyle="rgba(48,73,81,.82)";output.lineWidth=2.0;output.lineCap="round";
    const start=point([542,534]),end=point([690,490]);
    for(let i=0;i<3;i++){
      const x=start[0]+(end[0]-start[0])*p-i*12;
      const y=start[1]+(end[1]-start[1])*p+7*Math.sin(i*2)+3*Math.sin(t*1.5+i);
      const wing=4.0+3.2*Math.sin(t*10+i*1.5),span=7.2-i*.8;
      output.beginPath();output.moveTo(x-span,y-wing);
      output.quadraticCurveTo(x-span*.5,y-wing*.25,x,y);
      output.quadraticCurveTo(x+span*.5,y-wing*.25,x+span,y-wing);
      output.stroke();
    }
    output.restore();
  }
  function render(t) {
    output.clearRect(0,0,W,H);
    const wind=windAt(t)*(preference.matches?.76:1);
    safeEffect("rideau",()=>prepared.curtains.forEach(q=>paintCurtain(q,t,wind)));
    safeEffect("projections",()=>prepared.lights.forEach((q,i)=>paintFeature(q,
      AMPLITUDE.lightX*wind+5*Math.sin(t*.49+i),
      AMPLITUDE.lightY*wind+3*Math.sin(t*.38+i),.74+.25*Math.sin(t*.62+i),0)));
    safeEffect("lumière",()=>paintAmbientLight(t,wind));
    safeEffect("branches",()=>prepared.branches.forEach((q,i)=>paintFeature(q,
      AMPLITUDE.branchX*wind+2.5*Math.sin(t*.94+i*.23),
      AMPLITUDE.branchY*wind+1.8*Math.sin(t*.73+i*.29),1,0)));
    safeEffect("oiseaux",()=>paintBirds(t));
    safeEffect("poussières",()=>paintDust(t,wind));
  }
  function tick(now) {
    frame=null;
    if(last!==null)elapsed+=Math.min(250,Math.max(0,now-last));
    last=now;
    if(now-lastPaint>=FRAME_MS-.5){
      try{render(elapsed/1000);lastPaint=now;}
      catch(error){stop();report("unavailable","Rendu des animations indisponible.");console.warn("Portrait motion stopped:",error);return;}
    }
    frame=requestAnimationFrame(tick);
  }
  function stop() {
    if(frame!==null)cancelAnimationFrame(frame);
    frame=null;last=null;lastPaint=-Infinity;canvas.hidden=true;
  }
  function sync() {
    const enabled=toggle?toggle.checked:true;
    const inBedroom=room.dataset.room==="bedroom";
    if(inBedroom&&enabled&&visible&&!document.hidden&&!backdrop.naturalWidth){
      stop();
      if(backdrop.complete)report("unavailable","Décor de la chambre indisponible.");
      else report("loading");
      return;
    }
    const running=shouldRun(Boolean(backdrop.naturalWidth),inBedroom,visible,document.hidden,enabled);
    if(!running){stop();report("paused");return;}
    prepare();
    if(!prepared){stop();report("loading");return;}
    canvas.hidden=false;
    const counts=prepared.curtains.length+prepared.lights.length+prepared.branches.length;
    const partial=prepared.pixelFallback||disabledEffects.size>0||counts<3;
    report(partial?"partial":"active",partial?"Animations actives, certains calques indisponibles.":"");
    if(frame===null)frame=requestAnimationFrame(tick);
  }
  room.addEventListener("jade-room-changed",sync);
  backdrop.addEventListener("load",sync);
  backdrop.addEventListener("error",sync);
  document.addEventListener("visibilitychange",sync);
  if(preference.addEventListener)preference.addEventListener("change",sync);
  else preference.addListener(sync);
  if(typeof IntersectionObserver==="function"){
    new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync();}).observe(room);
  }
  sync();
})();
