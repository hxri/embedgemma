"""Drive the spoken-search page headlessly: start the recorder with the fake mic, stop after 3 s, read results."""
import base64, json, subprocess, time, urllib.request
import websocket
chrome = subprocess.Popen(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required", "--remote-debugging-port=9334",
    "--remote-allow-origins=*", "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
mid = 0
try:
    for _ in range(60):
        try: tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json")); break
        except Exception: time.sleep(0.25)
    ws = websocket.create_connection([t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"])
    def send(m, p=None):
        global mid; mid += 1; ws.send(json.dumps({"id": mid, "method": m, "params": p or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == mid: return r
    def js(e): return send("Runtime.evaluate", {"expression": e, "returnByValue": True, "awaitPromise": True})["result"].get("result", {}).get("value")
    send("Page.enable"); send("Runtime.enable"); send("Page.navigate", {"url": "http://127.0.0.1:8787/say/"}); time.sleep(2)
    print("state:", js("__say.state"), "| status:", js("document.getElementById('status').textContent"))
    js("__say.start()"); time.sleep(1.5); print("after start:", js("__say.state"), "|", js("document.getElementById('talkLabel').textContent"))
    time.sleep(2); js("__say.stop()")
    for _ in range(30):
        time.sleep(0.5)
        if js("__say.state") == "idle" and js("!document.getElementById('results').hidden"): break
    print("after stop:", js("__say.state"), "| status:", js("document.getElementById('status').textContent"))
    print("heard:", js("document.getElementById('heard').textContent"), "| best:", js("document.getElementById('bestCaption').textContent"))
    print("tiles:", js("document.querySelectorAll('.tile').length"), "| replay hidden:", js("document.getElementById('replay').hidden"))
    open("/tmp/e2e-say.png", "wb").write(base64.b64decode(send("Page.captureScreenshot", {"format": "png"})["result"]["data"]))
finally:
    chrome.terminate()
