"""Blender EEVEE render worker on GPU -> video, sent to Telegram.

input:
  blend        : .blend file URL or data: URI (optional if script builds the scene)
  script       : Python run inside Blender before rendering (build/animate scene)
  files        : {"name": url|data-uri} extra assets saved next to the .blend (models, textures, audio)
  frame_start, frame_end, fps (default 24), width/height (default 1080x1920)
  transparent  : render with alpha -> .webm (VP9 alpha) sent as a file; else .mp4
  audio        : file name in files (or URL) muxed into the mp4
  telegram     : default true; chat_id, caption
  mode         : "warm" | "eevee_probe" (GPU + EEVEE self-test); motion jobs (bundle/html) and "probe" go to Chromium
"""
import os, time, base64, subprocess, tempfile, shutil, glob, json
import requests, runpod

BLENDER = "/opt/blender/blender"

SETUP = r'''
import bpy, json, os
cfg = json.loads(os.environ["RENDER_CFG"])
sc = bpy.context.scene
try:
    sc.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = cfg["w"], cfg["h"]
sc.render.resolution_percentage = 100
sc.render.fps = cfg["fps"]
sc.frame_start, sc.frame_end = cfg["s"], cfg["e"]
sc.render.film_transparent = cfg["alpha"]
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA" if cfg["alpha"] else "RGB"
sc.render.filepath = cfg["out"] + "/f_"
if cfg.get("script"):
    exec(compile(open(cfg["script"]).read(), "user_script", "exec"), {"bpy": bpy, "__name__": "__main__"})
'''


def fetch(src, dest):
    if src.startswith("data:"):
        data = base64.b64decode(src.split(",", 1)[1])
    else:
        r = requests.get(src, timeout=300); r.raise_for_status(); data = r.content
    with open(dest, "wb") as f:
        f.write(data)


def tg_send(path, a, video):
    chat = str(a.get("chat_id") or os.environ["CHAT_ID"])
    method, field = ("sendVideo", "video") if video else ("sendDocument", "document")
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['BOT_TOKEN'].strip()}/{method}",
                          data={"chat_id": chat, "caption": a.get("caption", ""), "supports_streaming": "true"},
                          files={field: (os.path.basename(path), f)}, timeout=600)
    j = r.json()
    return j.get("ok"), j.get("description")


def work(a):
    mode = a.get("mode")
    if mode == "warm":
        return {"ok": True}
    t0 = time.monotonic()
    d = tempfile.mkdtemp()
    try:
        for name, src in (a.get("files") or {}).items():
            fetch(src, os.path.join(d, os.path.basename(name)))
        blend = None
        if a.get("blend"):
            blend = os.path.join(d, "scene.blend"); fetch(a["blend"], blend)
        script = None
        if mode == "eevee_probe" and not a.get("script"):
            a["script"] = ("import bpy\nob=bpy.data.objects.get('Cube')\n"
                           "ob.rotation_euler=(0,0,0); ob.keyframe_insert('rotation_euler',frame=1)\n"
                           "ob.rotation_euler=(0,0,6.283); ob.keyframe_insert('rotation_euler',frame=48)\n")
            a.setdefault("frame_end", 48); a.setdefault("caption", "Blender EEVEE probe")
        if a.get("script"):
            script = os.path.join(d, "user.py"); open(script, "w").write(a["script"])
        frames_dir = os.path.join(d, "frames"); os.makedirs(frames_dir)
        fps = int(a.get("fps", 24)); alpha = bool(a.get("transparent", False))
        cfg = {"w": int(a.get("width", 1080)), "h": int(a.get("height", 1920)), "fps": fps,
               "s": int(a.get("frame_start", 1)), "e": int(a.get("frame_end", 24)), "alpha": alpha,
               "out": frames_dir, "script": script}
        setup = os.path.join(d, "setup.py"); open(setup, "w").write(SETUP)
        cmd = [BLENDER, "-b"] + ([blend] if blend else []) + ["--python", setup, "-a"]
        env = dict(os.environ, RENDER_CFG=json.dumps(cfg))
        p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True)
        log_tail = (p.stdout + p.stderr)[-3000:]
        pngs = sorted(glob.glob(frames_dir + "/f_*.png"))
        if p.returncode or not pngs:
            raise RuntimeError("blender failed:\n" + log_tail)
        t_render = time.monotonic() - t0
        pattern = frames_dir + "/f_%04d.png"
        if alpha:
            out = os.path.join(d, "render.webm")
            enc = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-start_number", str(cfg["s"]),
                   "-i", pattern, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                   "-row-mt", "1", out]
        else:
            out = os.path.join(d, "render.mp4")
            enc = ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-start_number", str(cfg["s"]),
                   "-i", pattern]
            if a.get("audio"):
                ap = os.path.join(d, os.path.basename(a["audio"]))
                if not os.path.exists(ap):
                    ap = os.path.join(d, "audio_in"); fetch(a["audio"], ap)
                enc += ["-i", ap, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
            enc += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out]
        subprocess.run(enc, check=True)
        res = {"frames": len(pngs), "render_seconds": round(t_render, 2),
               "sec_per_frame": round(t_render / len(pngs), 3),
               "total_seconds": round(time.monotonic() - t0, 2), "bytes": os.path.getsize(out)}
        if mode == "eevee_probe":
            res["gpu"] = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                        capture_output=True, text=True).stdout.strip()
            res["engine_log"] = [l for l in log_tail.splitlines() if "EEVEE" in l or "GPU" in l or "EGL" in l][-8:]
        if a.get("telegram", True):
            res["telegram_ok"], err = tg_send(out, a, video=not alpha)
            if err:
                res["telegram_error"] = err
        return res
    finally:
        shutil.rmtree(d, ignore_errors=True)


def handler(job):
    a = job["input"]
    # Motion jobs (HTML/three.js) run in Chromium on this GPU; everything else is Blender.
    if a.get("bundle") or a.get("html") or a.get("html_url") or a.get("mode") == "probe":
        import motion_handler
        return motion_handler.handler(job)
    return work(a)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
