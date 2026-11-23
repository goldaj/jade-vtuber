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
let loadedApp = false, currentMode = "success", lastToken = null;
const requests = [], assets = [];
const window = {setTimeout:()=>1,clearTimeout(){}};
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
        window.JadeMobileApp = {login(token){
          lastToken=token;input.value="";feedback.textContent="";modal.classList.add("hidden");
        }};
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
  console.log("Mobile login OK: invalid/refused token loads zero app assets; authorized salon and deferred SDK");
})().catch(e=>{console.error(e);process.exitCode=1});
