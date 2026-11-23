/* Offline login browser contract: fake DOM and network, no private tokens. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const root = "src/jade_runtime/mobile_web/";
const html = fs.readFileSync(root + "index.html", "utf8");
const ids = [...html.matchAll(new RegExp('id="([^"]+)"', "g"))].map(m => m[1]);
const registry = new Map();
function node(id) {
  if (registry.has(id)) return registry.get(id);
  const handlers = {};
  const classes = new Set();
  const el = {
    id, value:"", disabled:false, textContent:"",
    dataset:{view:"home"}, open:false,
    classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),
      contains:x=>classes.has(x),toggle:(x,on)=>on?classes.add(x):classes.delete(x)},
    addEventListener:(event,cb)=>{(handlers[event]??=[]).push(cb)},
    setAttribute(){},removeAttribute(){},focus(){},replaceChildren(){},appendChild(){},
    querySelector:()=>node("submit-button"),
    handlers,classes
  };
  registry.set(id,el);
  return el;
}
ids.forEach(node);
const document={
  getElementById:node,
  querySelector:s=>s===".shell"?node("shell"):node(s),
  querySelectorAll:()=>[],addEventListener(){},hidden:false
};
const window={crypto:{randomUUID:()=>"a".repeat(32)},
  location:{hash:""},setTimeout:()=>1,clearTimeout(){},addEventListener(){},isSecureContext:true};
let response={status:200,ok:true,json:async()=>({status:"ok"})};
const fetch=async(path,opts)=>{
  assert.equal(path,"/api/auth");
  assert.equal(opts.method,"POST");
  assert.equal(opts.headers["Content-Type"],"application/json");
  assert.equal(opts.body,"{}");
  assert.match(opts.headers.Authorization,/^Bearer /);
  return response;
};
const context={document,window,navigator:{},crypto:window.crypto,fetch,
  setInterval(){},AbortController,Date,console};
vm.runInNewContext(fs.readFileSync(root+"login-guard.js","utf8"),context);
async function submit(value) {
  node("auth-token").value=value;
  const event={preventDefault(){this.prevented=true}};
  for(const callback of node("auth-form").handlers.submit) await callback(event);
  assert.equal(event.prevented,true);
}
(async()=>{
  await submit("x".repeat(40));
  assert.match(node("auth-feedback").textContent,/n'a pas pu démarrer/);
  vm.runInNewContext(fs.readFileSync(root+"app.js","utf8"),context);
  assert.equal(window.JadeAuthReady,true);
  await submit("short");
  assert.match(node("auth-feedback").textContent,/32 et 256/);
  response={status:401,ok:false,json:async()=>({error:"auth"})};
  await submit("x".repeat(40));
  assert.match(node("auth-feedback").textContent,/Jeton refusé/);
  assert.equal(node("auth-modal").classes.has("hidden"),false);
  response={status:200,ok:true,json:async()=>({status:"ok"})};
  await submit("x".repeat(40));
  assert.equal(node("auth-modal").classes.has("hidden"),true);
  assert.equal(node("auth-token").value,"");
  assert.equal(node("connection-status").textContent,"Connectée à Jade");
  console.log("Mobile login OK: script missing, invalid length, refused, accepted");
})().catch(e=>{console.error(e);process.exitCode=1});
