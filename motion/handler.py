"""Motion render worker: HTML (seek(t) + window.READY) -> MP4, rendered in parallel, sent to Telegram.

input:
  html        : page source (or html_url); optional when bundle has index.html
  bundle      : .tar.gz of a whole project (URL or data URI), extracted and served over http (ES modules, 3D models)
  page        : entry file inside the bundle (default index.html)
  files       : {"path/name": "https://..." | "data:...;base64,..."}  saved under the project folder
  audio       : file name inside files (or URL) muxed as the soundtrack
  dur, fps    : seconds, frames per second (default 30)
  width,height: default 1080x1920
  workers     : parallel browsers (default: cores//4, max 8)
  telegram    : send to Telegram (default true); chat_id, caption
  blender     : optional Blender stage run inside the extracted bundle BEFORE the page renders:
                {"script": "scene.py", "start": 1, "end": 240, "procs": 2, "stills": [frame,...]}
                The script gets env ASSET_DIR (bundle dir), PLATE_DIR (bundle/plate), FRAME_START/END and
                must render its own frames (e.g. plate/f_0001.jpg) for the page to load.
                With "stills", only those frames are rendered and returned as base64 JPEGs (no page render).
"""
import os, io, time, base64, subprocess, tempfile, shutil, tarfile, threading, functools, multiprocessing as mp
import http.server, socketserver
from concurrent.futures import ThreadPoolExecutor
import requests, runpod


def fetch(src, dest):
    if src.startswith("data:"):
        data = base64.b64decode(src.split(",", 1)[1])
    else:
        r = requests.get(src, timeout=120); r.raise_for_status(); data = r.content
    with open(dest, "wb") as f:
        f.write(data)


import json
BASE_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none", "--ignore-gpu-blocklist"]
# CPU default: SwiftShader. The GPU image sets CHROME_GL_ARGS to a hardware WebGL path.
GL_ARGS = BASE_ARGS + json.loads(os.environ.get("CHROME_GL_ARGS") or
                                 '["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]')

PROBE_JS = """() => { const c = document.createElement('canvas'); const g = c.getContext('webgl2') || c.getContext('webgl');
  if (!g) return 'no webgl'; const e = g.getExtension('WEBGL_debug_renderer_info');
  return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER) }"""


def probe(variants):
    """Which Chrome flags give hardware WebGL here? Returns the renderer string for each flag set."""
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        for v in variants:
            try:
                b = p.chromium.launch(args=BASE_ARGS + v)
                pg = b.new_page()
                out.append({"args": v, "renderer": pg.evaluate(PROBE_JS)})
                b.close()
            except Exception as e:
                out.append({"args": v, "error": str(e)[:300]})
    return out


def safe_path(root, name):
    p = os.path.normpath(os.path.join(root, name))
    if not p.startswith(os.path.abspath(root) + os.sep):
        raise ValueError("bad path: " + name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def serve(root):
    """Serve the project over http so ES modules, fetch() and 3D model loading work."""
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=root))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def render_range(args):
    from playwright.sync_api import sync_playwright
    path, out, fps, w, h, start, end, gl = args
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-vcodec", "mjpeg",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-threads", "4", out], stdin=subprocess.PIPE)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=gl)
            page = b.new_page(viewport={"width": w, "height": h})
            page.goto(path)
            page.wait_for_function("window.READY===true", timeout=180000)
            for i in range(start, end):
                page.evaluate("(t)=>seek(t)", i / fps)
                enc.stdin.write(page.screenshot(type="jpeg", quality=94))
            b.close()
        enc.stdin.close()
        if enc.wait():
            raise RuntimeError("encode failed")
    finally:
        if enc.poll() is None:
            enc.kill(); enc.wait()
    return out


BLENDER = "/opt/blender/blender"


def run_blender(d, b):
    plate = os.path.join(d, "plate"); os.makedirs(plate, exist_ok=True)
    script = safe_path(d, b.get("script", "scene.py"))
    def go(rng):
        env = dict(os.environ, ASSET_DIR=d, PLATE_DIR=plate, FRAME_START=str(rng[0]), FRAME_END=str(rng[1]),
                   STILLS=json.dumps(b.get("stills") or []))
        p = subprocess.run([BLENDER, "-b", "--python", script], cwd=d, env=env, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError("blender failed:\n" + (p.stdout + p.stderr)[-3000:])
        return (p.stdout + p.stderr)[-600:]
    if b.get("stills"):
        return [go((0, 0))]
    s0, e0 = int(b["start"]), int(b["end"]); k = max(1, int(b.get("procs", 1)))
    step = -(-(e0 - s0 + 1) // k)
    rngs = [(s0 + i * step, min(e0, s0 + (i + 1) * step - 1)) for i in range(k) if s0 + i * step <= e0]
    with ThreadPoolExecutor(len(rngs)) as ex:
        return list(ex.map(go, rngs))


def work(a):
    if a.get("mode") == "warm":
        return {"ok": True}
    if a.get("mode") == "probe":
        return {"probe": probe(a.get("variants") or [GL_ARGS[len(BASE_ARGS):]])}
    gl = BASE_ARGS + a["chrome_args"] if a.get("chrome_args") else GL_ARGS
    t0 = time.monotonic()
    fps = int(a.get("fps", 30)); dur = float(a.get("dur", 5))
    w = int(a.get("width", 1080)); h = int(a.get("height", 1920))
    if not (1 <= fps <= 60 and 0.1 <= dur <= 900):
        raise ValueError("invalid fps or duration")
    d = tempfile.mkdtemp()
    srv = None
    try:
        if a.get("bundle"):
            tgz = os.path.join(d, "_bundle.tgz"); fetch(a["bundle"], tgz)
            with tarfile.open(tgz) as tf:
                tf.extractall(d, filter="data")
            os.remove(tgz)
        for name, src in (a.get("files") or {}).items():
            fetch(src, safe_path(d, name))
        if a.get("blender"):
            tb = time.monotonic()
            logs = run_blender(d, a["blender"])
            if a["blender"].get("stills"):
                pl = os.path.join(d, "plate")
                return {"blender_seconds": round(time.monotonic() - tb, 2), "log": logs[-1][-400:],
                        "stills": {f: base64.b64encode(open(os.path.join(pl, f), "rb").read()).decode()
                                   for f in sorted(os.listdir(pl)) if f.endswith(".jpg")}}
            blender_seconds = round(time.monotonic() - tb, 2)
        page_name = a.get("page", "index.html")
        if a.get("html_url"):
            fetch(a["html_url"], safe_path(d, page_name))
        elif a.get("html"):
            open(safe_path(d, page_name), "w").write(a["html"])
        srv = serve(d)
        path = f"http://127.0.0.1:{srv.server_address[1]}/{page_name}"
        frames = round(dur * fps)
        n = int(a.get("workers") or max(1, min(8, (os.cpu_count() or 4) // 4)))
        n = max(1, min(n, frames // 15 or 1))
        step = -(-frames // n)
        segdir = tempfile.mkdtemp()
        jobs = [(path, os.path.join(segdir, f"seg{k:02d}.mp4"), fps, w, h, k * step, min(frames, (k + 1) * step), gl)
                for k in range(n) if k * step < frames]
        with mp.get_context("spawn").Pool(len(jobs)) as pool:
            segs = pool.map(render_range, jobs)
        t_render = time.monotonic() - t0
        lst = os.path.join(segdir, "list.txt")
        open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
        out = os.path.join(segdir, "video.mp4")
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst]
        audio = a.get("audio")
        if audio:
            if audio.startswith(("http", "data:")):
                ap = os.path.join(segdir, "audio_in"); fetch(audio, ap)
            else:
                ap = safe_path(d, audio)
            cmd += ["-i", ap, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "copy", "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)
        res = {"frames": frames, "workers": len(jobs), "render_seconds": round(t_render, 2),
               "blender_seconds": locals().get("blender_seconds"),
               "total_seconds": round(time.monotonic() - t0, 2), "bytes": os.path.getsize(out)}
        if a.get("telegram", True):
            chat = str(a.get("chat_id") or os.environ["CHAT_ID"])
            # Telegram bots can't send files over 50 MB: re-encode to fit
            send = out
            if os.path.getsize(out) > 48_000_000:
                send = os.path.join(segdir, "tg.mp4")
                kbps = int(45_000_000 * 8 / 1000 / max(dur, 1)) - 160
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-c:v", "libx264", "-preset", "fast",
                                "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps*1.3)}k", "-bufsize", f"{kbps*2}k",
                                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", send], check=True)
                res["tg_bytes"] = os.path.getsize(send)
            with open(send, "rb") as f:
                r = requests.post("https://api.telegram.org/bot" + os.environ["BOT_TOKEN"].strip() + "/sendVideo",
                                  data={"chat_id": chat, "caption": a.get("caption", ""), "supports_streaming": "true",
                                        "width": str(w), "height": str(h)},
                                  files={"video": ("video.mp4", f, "video/mp4")}, timeout=600)
            j = r.json(); res["telegram_ok"] = j.get("ok")
            if not j.get("ok"):
                res["telegram_error"] = j.get("description")
        elif res["bytes"] <= 7_000_000:
            res["video_base64"] = base64.b64encode(open(out, "rb").read()).decode()
        if a.get("preview"):
            # small copy so Claude can check the final render before it goes out
            pv = os.path.join(segdir, "preview.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-vf", "scale=360:640", "-r", "15",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "33", "-c:a", "aac", "-b:a", "48k", pv], check=True)
            if os.path.getsize(pv) <= 7_000_000:
                res["preview_base64"] = base64.b64encode(open(pv, "rb").read()).decode()
            else:
                res["preview_error"] = "preview too large"
        return res
    finally:
        if srv:
            srv.shutdown()
        shutil.rmtree(d, ignore_errors=True)
        if "segdir" in locals():
            shutil.rmtree(segdir, ignore_errors=True)


def handler(job):
    # Playwright's sync API refuses to run inside runpod's asyncio loop, so work happens in a thread.
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(work, job["input"]).result()


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
