"""Offline, r21-only browser recipe using the application's real renderer.

Requires Playwright, Chromium and the licensed Web SDK from a Jade installation.
No Jade server, account, microphone, supplier or external request is used. Audio
is an explicitly synthetic Web Audio signal, not a validation of the TTS voice.
Example:
  python tools/jade_r21_visual_qa.py --sdk-dir /path/to/vendor \
    --chromium /usr/bin/chromium --output /path/to/qa-results
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src/jade_runtime/mobile_web"
BUNDLE = ROOT / "jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Jade_r21_v45"
MANIFEST = "Jade_r21_mobile.model3.json"
INTENTS = ("neutral", "playful", "excited", "curious", "tender", "reassuring", "serious", "sad", "angry")

CAPTURE_SCRIPT = r"""
const load = PIXI.live2d.Live2DModel.fromSync;
PIXI.live2d.Live2DModel.fromSync = function(...args) {
  const model = load.apply(this,args);
  window.__qaModel = model;
  window.__qaCalls = [];
  const motion = model.motion;
  model.motion = function(group,index,...rest) {
    __qaCalls.push({group,index,at:performance.now()});
    return motion.call(this,group,index,...rest);
  };
  return model;
};
window.__qaAttach = () => {
  const model=__qaModel, core=model.internalModel.coreModel;
  // Inject a closed blink after the blink engine, before Jade's held face.
  // The later snapshot observes the application's multiplication and audio.
  model.internalModel.on('afterMotionUpdate',()=> {
    if(window.__qaCloseEyes) {
      core.setParameterValueById('ParamEyeLOpen',0);
      core.setParameterValueById('ParamEyeROpen',0);
    }
  });
  model.internalModel.on('beforeModelUpdate',()=> {
    window.__qaFrame = Object.fromEntries([
      'ParamMouthOpenY','ParamMouthForm','ParamEyeLOpen','ParamEyeROpen',
      'ParamAngleX','ParamAngleY','ParamAngleZ','ParamBrowLAngle','ParamBrowRAngle',
      'ParamJadeEarFollowL','ParamJadeEarFollowR'
    ].map(id=>[id,core.getParameterValueById(id)]));
  });
};
window.__qaBegin = async (intent,variant) => {
  window.__qaCloseEyes=false;
  JadeAvatar.resetIntent();
  JadeAvatar.setMouth(0);
  JadeAvatar.setSpeaking(false);
  const originalRandom=Math.random;
  Math.random=()=>variant ? .8 : .2;
  try { JadeAvatar.setIntent(intent,{deferMotion:true}); }
  finally { Math.random=originalRandom; }
  await new Promise(resolve=>setTimeout(resolve,200));
  const AudioContext=window.AudioContext||window.webkitAudioContext;
  const context=window.__qaAudio ||= new AudioContext();
  await context.resume();
  const oscillator=context.createOscillator(),gain=context.createGain(),analyser=context.createAnalyser();
  oscillator.frequency.value=240;
  gain.gain.value=.08;
  analyser.fftSize=256;
  oscillator.connect(gain);gain.connect(analyser);analyser.connect(context.destination);
  oscillator.start();
  const signal=new Float32Array(analyser.fftSize);
  const start=performance.now();
  window.__qaPlaying=true;
  const tick=()=> {
    if(!window.__qaPlaying)return;
    const age=(performance.now()-start)/1000;
    gain.gain.value=window.__qaPause?0:.045+.035*Math.sin(age*13)**2;
    analyser.getFloatTimeDomainData(signal);
    const rms=Math.sqrt(signal.reduce((total,x)=>total+x*x,0)/signal.length);
    JadeAvatar.setMouth(Math.min(1,rms*13));
    requestAnimationFrame(tick);
  };
  window.__qaPause=false;
  window.__qaStopSignal=()=>{window.__qaPlaying=false;oscillator.stop();oscillator.disconnect();
    gain.disconnect();analyser.disconnect();JadeAvatar.setMouth(0);};
  JadeAvatar.setSpeaking(true);JadeAvatar.startReplyMotion();tick();
};
window.__qaEnd=()=>{window.__qaStopSignal?.();JadeAvatar.setSpeaking(false);JadeAvatar.finishReply(true);};
window.__qaSnapshot=()=> {
  const raw=__qaModel.internalModel.coreModel.getModel();
  const eyes={};
  for(const side of ['L','R']) {
    for(const part of ['SOCKET_SKIN','CLOSED_TRUE']) {
      const id=`JAD_R21_EYE_${side}_${part}`,index=raw.drawables.ids.indexOf(id);
      eyes[id]=raw.drawables.opacities[index];
    }
  }
  return {state:JadeAvatar.state,frame:window.__qaFrame,eyes,
    room:document.querySelector('.room').dataset.room,
    view:document.querySelector('.shell').dataset.view,
    full:document.querySelector('.shell').classList.contains('is-room-only'),
    calls:__qaCalls.slice(),canvasCount:document.querySelectorAll('#avatar-container canvas').length};
};
"""


def html_page() -> bytes:
    scripts = ("/assets/room-motion.js", "/assets/avatar-models.js",
               "/vendor/pixi.min.js", "/vendor/unsafe-eval.min.js",
               "/vendor/live2dcubismcore.min.js", "/vendor/pixi-live2d-display.min.js",
               "/assets/avatar-model-loader.js")
    tags = "".join(f'<script src="{src}"></script>' for src in scripts)
    return ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<link rel='stylesheet' href='/assets/styles.css'>"
            "<link rel='stylesheet' href='/assets/jade-theme.css'>"
            "<title>Recette locale r21</title></head><body>"
            + (WEB / "salon.html").read_text(encoding="utf-8") + tags
            + "<script>" + CAPTURE_SCRIPT + "</script>"
            "<script src='/assets/avatar.js'></script></body></html>").encode()


def handler_for(sdk: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.send_error(403, "Offline recipe: no runtime or provider")

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            content_type = "application/json"
            if path == "/":
                data, content_type = html_page(), "text/html; charset=utf-8"
            elif path == "/assets/avatar-models.json":
                data = json.dumps({"version": 1, "defaultId": "next", "models": [
                    {"id": "classic", "label": "Ancien modèle", "available": True,
                     "manifestUrl": "/model/Jade.model3.json", "presentation": "seated",
                     "classicIntents": True, "idleMotion": "Idle"},
                    {"id": "next", "label": "Jade r21", "available": True,
                     "manifestUrl": "/models/next/Jade.model3.json", "presentation": "full",
                     "classicIntents": False, "idleMotion": "Idle"},
                ]}).encode()
            elif path == "/assets/intent-visuals.json":
                palette = json.loads((WEB / "intent-visuals.json").read_text())
                data = json.dumps({**palette, "enabled": True}).encode()
            else:
                filename = None
                for prefix, folder in (("/assets/", WEB), ("/vendor/", sdk), ("/models/next/", BUNDLE)):
                    if path.startswith(prefix):
                        name = path[len(prefix):]
                        if prefix == "/models/next/" and name == "Jade.model3.json":
                            name = MANIFEST
                        candidate = (folder / name).resolve()
                        if candidate.is_relative_to(folder.resolve()) and candidate.is_file():
                            filename = candidate
                if path == "/icon.svg":
                    filename = WEB / "icon.svg"
                if filename is None:
                    self.send_error(404)
                    return
                data = filename.read_bytes()
                if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
                    self.send_error(503, "Hydrate the r21 Git LFS resource first")
                    return
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-dir", type=Path, required=True)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--new-only", action="store_true")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    args.output.mkdir(parents=True, exist_ok=True)
    report = {"result": "INCOMPLETE", "model": "r21", "audio": "synthetic Web Audio only",
              "blink": "closed blink injected before the application's held face",
              "viewport": {"width": 393, "height": 873}, "cases": [], "layouts": [],
              "pageErrors": [], "failedRequests": [], "r20Requests": [], "blockedRequests": []}
    manifest = json.loads((BUNDLE / MANIFEST).read_text())
    moc = BUNDLE / manifest["FileReferences"]["Moc"]
    report["mocSha256"] = hashlib.sha256(moc.read_bytes()).hexdigest()
    report["manifestSha256"] = hashlib.sha256((BUNDLE / MANIFEST).read_bytes()).hexdigest()
    report["avatarSha256"] = hashlib.sha256((WEB / "avatar.js").read_bytes()).hexdigest()
    report["coreSha256"] = hashlib.sha256((args.sdk_dir / "live2dcubismcore.min.js").read_bytes()).hexdigest()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(args.sdk_dir))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.chromium, headless=True,
                args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                      "--autoplay-policy=no-user-gesture-required"])
            report["browser"] = browser.version
            context = browser.new_context(viewport={"width": 393, "height": 873},
                device_scale_factor=1, is_mobile=True, has_touch=True, service_workers="block")
            def local_requests_only(route):
                if route.request.url.startswith(url + "/"):
                    route.continue_()
                else:
                    report["blockedRequests"].append(route.request.url)
                    route.abort()
            context.route("**/*", local_requests_only)
            page = context.new_page()
            page.on("pageerror", lambda error: report["pageErrors"].append(str(error)))
            page.on("response", lambda response: report["failedRequests"].append(
                {"path": urlparse(response.url).path, "status": response.status}) if response.status >= 400 else None)
            page.on("request", lambda request: report["r20Requests"].append(request.url)
                if "/model/" in request.url else None)
            page.goto(url, wait_until="networkidle")
            page.wait_for_function("JadeAvatar?.state.status === 'ready' && JadeAvatar.state.modelId === 'next'")
            page.evaluate("__qaAttach()")
            for intent in (("sad", "angry") if args.new_only else INTENTS):
                for variant in (0, 1):
                    label = f"{intent}-{'B' if variant else 'A'}"
                    page.evaluate("__qaCalls.length=0")
                    page.evaluate("([intent,variant])=>__qaBegin(intent,variant)", [intent, variant])
                    page.wait_for_timeout(1150)
                    active = page.evaluate("__qaSnapshot()")
                    assert active["state"]["modelId"] == "next" and active["canvasCount"] == 1, active
                    assert active["frame"]["ParamMouthOpenY"] > .01, active
                    gestures = [call for call in active["calls"] if call["group"] != "Idle"]
                    assert len(gestures) == 1 and gestures[0]["index"] == variant and gestures[0]["group"] == intent.title(), gestures
                    page.screenshot(path=str(args.output / f"{label}.png"))
                    page.evaluate("window.__qaPause=true;window.__qaCloseEyes=true")
                    page.wait_for_timeout(160)
                    pause = page.evaluate("__qaSnapshot()")
                    assert pause["frame"]["ParamMouthOpenY"] < .001, pause
                    assert all(value > .99 if "CLOSED_TRUE" in name else value < .001
                               for name, value in pause["eyes"].items()), pause
                    if intent in ("sad", "angry"):
                        page.screenshot(path=str(args.output / f"{label}-closed.png"))
                    page.evaluate("window.__qaCloseEyes=false;__qaEnd()")
                    page.wait_for_timeout(950)
                    rest = page.evaluate("__qaSnapshot()")
                    assert rest["frame"]["ParamMouthOpenY"] < .001, rest
                    assert abs(rest["frame"]["ParamMouthForm"]) < .01, rest
                    report["cases"].append({"case": label, "active": active, "pause": pause, "rest": rest})
                    print(label, "PASS", flush=True)
            for room in ("bedroom", "kitchen", "living"):
                page.evaluate("()=>{const shell=document.querySelector('.shell');shell.dataset.view='home';shell.classList.remove('is-room-only');JadeAvatar.resize();}")
                page.select_option("#room-selector", room)
                page.wait_for_function("name=>document.querySelector('.room').dataset.room===name", arg=room)
                for view in ("home", "profile", "full"):
                    page.evaluate("view=>{const shell=document.querySelector('.shell');shell.dataset.view=view==='profile'?'profile':'home';shell.classList.toggle('is-room-only',view==='full');JadeAvatar.resize();}", view)
                    page.evaluate("__qaBegin('sad',0)")
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(args.output / f"layout-{room}-{view}.png"))
                    layout = page.evaluate("__qaSnapshot()")
                    assert layout["state"]["modelId"] == "next" and layout["state"]["status"] == "ready", layout
                    assert layout["room"] == room and layout["canvasCount"] == 1, layout
                    assert layout["full"] == (view == "full") and layout["view"] == ("profile" if view == "profile" else "home"), layout
                    report["layouts"].append({"room": room, "view": view, "state": layout})
                    page.evaluate("__qaEnd()")
            assert not report["pageErrors"], report["pageErrors"]
            assert not report["r20Requests"], report["r20Requests"]
            assert not report["failedRequests"], report["failedRequests"]
            assert not report["blockedRequests"], report["blockedRequests"]
            report["result"] = "PASS"
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(report["cases"]), "layouts": len(report["layouts"]),
                      "pageErrors": report["pageErrors"], "r20Requests": report["r20Requests"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
