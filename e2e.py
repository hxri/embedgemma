"""Drive headless Chrome over DevTools to run a full take with the fake camera and mic."""
import base64, json, subprocess, sys, time, urllib.request
import websocket

URL = "http://127.0.0.1:8787/?shot=1&autorun=1"
chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
    "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required",
    "--remote-debugging-port=9333", "--remote-allow-origins=*", "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
mid = 0
try:
    tabs = None
    for _ in range(60):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json")); break
        except Exception:
            time.sleep(0.25)
    page = [t for t in tabs if t["type"] == "page"][0]
    ws = websocket.create_connection(page["webSocketDebuggerUrl"])
    def send(method, params=None):
        global mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid:
                return m
    def js(expr):
        r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r["result"].get("result", {}).get("value")
    send("Page.enable"); send("Runtime.enable")
    send("Page.navigate", {"url": URL})
    t0 = time.time(); last = None
    while time.time() - t0 < 75:
        v = js("document.body.dataset.state + ' | ' + document.getElementById('loopLabel').textContent + ' | ' + document.getElementById('tc').textContent + ' | ' + (document.getElementById('bandNote').hidden ? '' : document.getElementById('bandNote').textContent)")
        if v != last:
            print(f"{time.time() - t0:5.1f}s  {v}", flush=True); last = v
        if v and (v.startswith("playing") or v.startswith("error")):
            break
        time.sleep(0.5)
    time.sleep(2.5)
    print(js("JSON.stringify({state: document.body.dataset.state, lines: [...document.querySelectorAll('.line')].map(b => b.getAttribute('aria-label')), paused: document.getElementById('take').paused, t: document.getElementById('take').currentTime.toFixed(2), src: document.getElementById('take').currentSrc, sound: __rythmo.player.current, ctx: __rythmo.player.ctx.state, trace: __rythmo.current && __rythmo.current.trace.length, errors: window.__errors})"))
    shot = send("Page.captureScreenshot", {"format": "png"})
    open("/tmp/e2e-playing.png", "wb").write(base64.b64decode(shot["result"]["data"]))
    print("screenshot /tmp/e2e-playing.png")
finally:
    chrome.terminate()
