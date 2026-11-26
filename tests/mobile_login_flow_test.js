/* Browser-free contract: no salon assets before verified token and no SDK on login. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const root = "src/jade_runtime/mobile_web/";
const index = fs.readFileSync(root+"index.html","utf8");
const salon = fs.readFileSync(root+"salon.html","utf8");
const js = fs.readFileSync(root+"login-guard.js","utf8");
assert(index.includes('src="/assets/login-guard.js"'));
assert(!index.includes('src="/assets/app.js"'));
assert(!index.includes('src="/vendor/'));
assert(!index.includes('href="/assets/styles.css"'));
assert(!index.includes('id="avatar-container"'));
assert(salon.includes('id="avatar-container"'));
const handlers = {}, classes = new Set();
const modal = {classList:{add(x){classes.add(x)},remove(x){classes.delete(x)}}};
const input = {value:"",focus(){}}, feedback = {textContent:""};
const button = {disabled:false};
const form = {
  querySelector:()=>button,
  addEventListener:(type,fn)=>{handlers[type]=fn}
};
let loadedApp = false, currentMode = "success", lastToken = null, liveLoadMode = "error", timerId = 0;
const requests = [], assets = [], liveEvents = [], timers = new Map();
const window = {setTimeout(fn){timers.set(++timerId, fn);return timerId;},clearTimeout(id){timers.delete(id);}};
const document = {
  getElementById(id){return ({
    "auth-form":form, "auth-token":input,"auth-feedback":feedback,
    "auth-modal":modal
  })[id]||null},
  querySelector(sel){return sel===".shell" && loadedApp ? {} : null},
  createElement(tag){
    if(tag==="template")return {innerHTML:"",content:{querySelector:()=>({})}};
    return {tag};
  },
  head:{appendChild(element){
    assets.push(element.href||element.src);
    queueMicrotask(()=>{
      if(element.src==="/assets/app.js"){
        window.JadeMobileApp = {
          liveModuleLoading(){liveEvents.push("loading");},
          liveModuleFailed(){liveEvents.push("failed");},
          liveModuleReady(){liveEvents.push("ready");},
          login(token){
          lastToken=token;input.value="";feedback.textContent="";modal.classList.add("hidden");
        }};
      }
      if(element.src==="/assets/live-client.js"){
        if(liveLoadMode==="error"){element.onerror();return;}
        if(liveLoadMode==="timeout")return;
        window.JadeLive={create(){}};
      }
      element.onload();
    });
  }},
  body:{insertBefore(){loadedApp=true}}
};
const fetch=async(url, options)=>{
  requests.push({url,method:options.method});
  if(url==="/api/auth"){
    assert.equal(options.method,"POST");
    assert.equal(options.headers["Content-Type"],"application/json");
    assert.equal(options.body,"{}");
    assert.match(options.headers.Authorization,/^Bearer /);
    if(currentMode==="refused")return {status:401,ok:false};
    return {status:200,ok:true,json:async()=>({status:"ok"})};
  }
  assert.equal(url,"/assets/salon.html");
  assert.equal(options.method,"GET");
  assert.match(options.headers.Authorization,/^Bearer /);
  return {status:200,ok:true,text:async()=>salon};
};
vm.runInNewContext(js,{document,window,fetch,AbortController,console});
async function submit(value){
  input.value=value;
  const event={preventDefault(){this.prevented=true}};
  await handlers.submit(event);
  assert.equal(event.prevented,true);
}
(async()=>{
  assert.deepEqual(assets,[]);
  await submit("short");
  assert.match(feedback.textContent,/32 et 256/);
  assert.deepEqual(requests,[]);
  currentMode="refused";
  await submit("x".repeat(40));
  assert.match(feedback.textContent,/Jeton refusé/);
  assert.equal(requests.length,1);
  assert.deepEqual(assets,[]);
  currentMode="success";
  await submit("x".repeat(40));
  assert.equal(lastToken,"x".repeat(40));
  assert.equal(classes.has("hidden"),true);
  assert.equal(requests[2].url,"/assets/salon.html");
  assert(assets.includes("/assets/styles.css"));
  assert(assets.includes("/assets/jade-theme.css"));
  assert(assets.includes("/assets/app.js"));
  assert.equal(button.disabled,false);
  await new Promise(resolve=>setImmediate(resolve));
  assert(assets.indexOf("/vendor/pixi.min.js") > assets.indexOf("/assets/app.js"));
  const catalogue = assets.indexOf("/assets/avatar-models.js");
  const loader = assets.indexOf("/assets/avatar-model-loader.js");
  assert(catalogue > assets.indexOf("/assets/app.js"), "catalogue loads only after private login");
  assert(catalogue < assets.indexOf("/assets/seated-scene.js"), "seated scene sees the catalogue");
  assert(loader > assets.indexOf("/vendor/cubism4.min.js"), "model loader receives the complete SDK");
  assert(loader < assets.indexOf("/assets/avatar.js"), "renderer receives its selection loader");
  assert(assets.indexOf("/assets/avatar-gestures.js") > assets.indexOf("/assets/avatar.js"),
    "touch gestures load after the renderer");
  assert(assets.indexOf("/assets/avatar-shake.js") > assets.indexOf("/assets/avatar-gestures.js"),
    "device motion loads after touch gestures and the renderer");
  assert(assets.indexOf("/assets/live-client.js") < assets.indexOf("/assets/duplex-client.js"),
    "Live loads directly after authentication without waiting for optional classic or visual modules");
  assert.equal(liveEvents.at(-1), "failed", "a missing Live asset is reported explicitly");
  liveLoadMode="timeout";
  const timedOut=window.JadeLogin.retryLive();
  assert.equal(window.JadeLogin.retryLive(), timedOut, "concurrent retry does not load a second module");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(timers.size, 1);
  [...timers.values()][0]();
  assert.equal(await timedOut, false);
  assert.equal(liveEvents.at(-1), "failed", "a stalled module has a bounded failure state");
  liveLoadMode="success";
  assert.equal(await window.JadeLogin.retryLive(), true);
  assert.equal(assets.filter(asset=>asset==="/assets/live-client.js").length, 3);
  assert.equal(await window.JadeLogin.retryLive(), true);
  assert.equal(liveEvents.at(-1), "ready");
  assert.equal(assets.filter(asset=>asset==="/assets/live-client.js").length, 3,
    "a ready Live module is reused, preserving its existing client");
  assert.equal(requests.filter(request=>request.url==="/api/auth").length, 2,
    "retry does not request or persist another bearer token");
  console.log("Mobile login OK: invalid/refused token loads zero app assets; authorized salon and deferred SDK");
})().catch(e=>{console.error(e);process.exitCode=1});
