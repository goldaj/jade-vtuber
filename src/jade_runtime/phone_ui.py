"""Local phone/desktop chat UI, self-contained and offline-compatible.

Never store the HTTP bearer token in localStorage, sessionStorage or cookies.
"""
PHONE_HTML = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Jade · Client local</title>
<style>
:root{font-family:system-ui;color-scheme:dark;background:#12121b;color:#f5f2ff}
*{box-sizing:border-box}body{margin:0}
main{max-width:720px;height:100dvh;margin:auto;display:flex;flex-direction:column}
header{padding:1rem;display:flex;align-items:center;border-bottom:1px solid #444051;gap:1rem}
h1{margin:0;flex:1;font-size:1.2rem}button{border:0;border-radius:.7rem;padding:.7rem 1rem;background:#a88ff4;color:#191125;font:inherit;font-weight:bold;cursor:pointer}
button:disabled{opacity:.5;cursor:default}button.secondary{background:#393548;color:white}
#messages{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.8rem}
.message{padding:.85rem 1rem;max-width:90%;border-radius:1rem;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5}
.me{align-self:end;background:#44365f}.jade{align-self:start;background:#262638}
footer{padding:1rem;border-top:1px solid #444051;display:grid;gap:.6rem}
label{font-size:.85rem;color:#c1bacd}input,textarea{width:100%;border:1px solid #625b74;border-radius:.7rem;background:#20202c;color:#fff;padding:.7rem;font:inherit}
textarea{resize:vertical;min-height:4rem;max-height:10rem}
.actions{display:flex;gap:1rem;align-items:center}.actions button{margin-left:auto}
#status{font-size:.85rem;color:#c1bacd}
:focus-visible{outline:2px solid #cab4ff;outline-offset:2px}
</style></head>
<body><main>
<header><h1>Jade · Client local</h1><button id="new" type="button" class="secondary">Nouvelle discussion</button></header>
<section id="messages" role="log" aria-label="Conversation" aria-live="polite"></section>
<footer>
<label for="token">Jeton privé (jamais enregistré)</label>
<input id="token" type="password" autocomplete="off" spellcheck="false" placeholder="JADE_HTTP_TOKEN">
<label for="message">Message</label>
<textarea id="message" maxlength="1200" placeholder="Bonjour Jade…"></textarea>
<div class="actions"><span id="status" role="status">Prêt. Saisissez votre jeton.</span><button id="send" type="button">Envoyer</button></div>
</footer></main>
<script>
"use strict";
const token=document.getElementById("token"),input=document.getElementById("message");
const messages=document.getElementById("messages"),status=document.getElementById("status");
const send=document.getElementById("send"),newButton=document.getElementById("new");
let busy=false;
function newSession(){return "web-"+crypto.randomUUID().replaceAll("-","").slice(0,24)}
let session=newSession();
function add(text,role){
 const div=document.createElement("div");div.className="message "+role;
 div.textContent=text; // Display untrusted user/model text without interpreting HTML.
 messages.appendChild(div);messages.scrollTop=messages.scrollHeight;
}
async function submit(){
 if(busy)return;
 const text=input.value.trim(),secret=token.value;
 if(!secret){status.textContent="Saisissez le jeton privé.";token.focus();return}
 if(!text)return;
 busy=true;send.disabled=true;newButton.disabled=true;
 status.textContent="Jade réfléchit…";add(text,"me");input.value="";
 try{
  const response=await fetch("/message",{
   method:"POST",
   headers:{"Content-Type":"application/json","Authorization":"Bearer "+secret},
   body:JSON.stringify({text:text,session:session}),cache:"no-store"
  });
  const result=await response.json();
  if(!response.ok)throw new Error(
   response.status===401?"Jeton invalide.":(result.error||"Erreur HTTP "+response.status));
  add(String(result.reply||""),"jade");status.textContent="Prêt.";
 }catch(err){status.textContent=err.message||"Connexion impossible."}
 finally{busy=false;send.disabled=false;newButton.disabled=false;input.focus()}
}
send.addEventListener("click",submit);
input.addEventListener("keydown",e=>{
 if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit()}
});
newButton.addEventListener("click",()=>{
 if(busy)return;
 session=newSession();messages.replaceChildren();status.textContent="Nouvelle discussion.";input.focus();
});
</script></body></html>
"""
