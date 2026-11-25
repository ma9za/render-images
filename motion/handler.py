"""Motion render worker: HTML (seek(t) + window.READY) -> MP4, rendered in parallel, sent to Telegram.

input:
  html        : page source (or html_url)
  files       : {"name": "https://..." | "data:...;base64,..."}  saved next to index.html
  audio       : file name inside files (or URL) muxed as the soundtrack
  dur, fps    : seconds, frames per second (default 30)
  width,height: default 1080x1920
  workers     : parallel browsers (default: cores//4, max 8)
  telegram    : send to Telegram (default true); chat_id, caption
"""
import os, time, base64, subprocess, tempfile, shutil, multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
import requests, runpod


def fetch(src, dest):
    if src.startswith("data:"):
        data = base64.b64decode(src.split(",", 1)[1])
    else:
        r = requests.get(src, timeout=120); r.raise_for_status(); data = r.content
    with open(dest, "wb") as f:
        f.write(data)


def render_range(args):
    from playwright.sync_api import sync_playwright
    path, out, fps, w, h, start, end = args
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-vcodec", "mjpeg",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-threads", "4", out], stdin=subprocess.PIPE)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"])
            page = b.new_page(viewport={"width": w, "height": h})
            page.goto("file://" + path)
            page.wait_for_function("window.READY===true", timeout=90000)
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


def work(a):
    if a.get("mode") == "warm":
        return {"ok": True}
    t0 = time.monotonic()
    fps = int(a.get("fps", 30)); dur = float(a.get("dur", 5))
    w = int(a.get("width", 1080)); h = int(a.get("height", 1920))
    if not (1 <= fps <= 60 and 0.1 <= dur <= 900):
        raise ValueError("invalid fps or duration")
    d = tempfile.mkdtemp()
    try:
        for name, src in (a.get("files") or {}).items():
            dest = os.path.join(d, os.path.basename(name)); fetch(src, dest)
        path = os.path.join(d, "index.html")
        if a.get("html_url"):
            fetch(a["html_url"], path)
        else:
            open(path, "w").write(a["html"])
        frames = round(dur * fps)
        n = int(a.get("workers") or max(1, min(8, (os.cpu_count() or 4) // 4)))
        n = max(1, min(n, frames // 15 or 1))
        step = -(-frames // n)
        jobs = [(path, os.path.join(d, f"seg{k:02d}.mp4"), fps, w, h, k * step, min(frames, (k + 1) * step))
                for k in range(n) if k * step < frames]
        with mp.get_context("spawn").Pool(len(jobs)) as pool:
            segs = pool.map(render_range, jobs)
        t_render = time.monotonic() - t0
        lst = os.path.join(d, "list.txt")
        open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
        out = os.path.join(d, "video.mp4")
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst]
        audio = a.get("audio")
        if audio:
            ap = os.path.join(d, os.path.basename(audio))
            if not os.path.exists(ap):
                ap = os.path.join(d, "audio_in"); fetch(audio, ap)
            cmd += ["-i", ap, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "copy", "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)
        res = {"frames": frames, "workers": len(jobs), "render_seconds": round(t_render, 2),
               "total_seconds": round(time.monotonic() - t0, 2), "bytes": os.path.getsize(out)}
        if a.get("telegram", True):
            chat = str(a.get("chat_id") or os.environ["CHAT_ID"])
            with open(out, "rb") as f:
                r = requests.post("https://api.telegram.org/bot" + os.environ["BOT_TOKEN"].strip() + "/sendVideo",
                                  data={"chat_id": chat, "caption": a.get("caption", ""), "supports_streaming": "true",
                                        "width": str(w), "height": str(h)},
                                  files={"video": ("video.mp4", f, "video/mp4")}, timeout=600)
            j = r.json(); res["telegram_ok"] = j.get("ok")
            if not j.get("ok"):
                res["telegram_error"] = j.get("description")
        elif res["bytes"] <= 7_000_000:
            res["video_base64"] = base64.b64encode(open(out, "rb").read()).decode()
        return res
    finally:
        shutil.rmtree(d, ignore_errors=True)


def handler(job):
    # Playwright's sync API refuses to run inside runpod's asyncio loop, so work happens in a thread.
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(work, job["input"]).result()


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
