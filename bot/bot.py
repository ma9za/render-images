"""@Codexmabot — receives Turki's voice, images and clips for the next video; finished videos come back here.

The current video's file list is kept as a pinned assets.json in the owner's chat, so nothing needs
paid storage and the render worker (or Claude) can read it with getChat -> pinned_message.
"""
import os, io, json, time, requests

TOKEN = os.environ["BOT_TOKEN"].strip()
OWNER = int(os.environ.get("OWNER_ID", "7732118455"))
API = f"https://api.telegram.org/bot{TOKEN}/"

MSG = {
    "start": (
        "هلا والله يا تركي 👋\n"
        "هذا بوت الرندر حقك.\n\n"
        "طريقة الشغل:\n"
        "1. أرسل صوت ElevenLabs\n"
        "2. أرسل الصور أو المقاطع إذا عندك\n"
        "3. ارجع لـ Claude وقل «سو الفيديو»\n\n"
        "والفيديو يوصلك هنا أول ما يخلص.\n\n"
        "/new فيديو جديد ويمسح الملفات الحالية\n"
        "/list وش استلمت للحين"
    ),
    "voice": "وصل الصوت ✅\nالمدة: {dur}\n\nإذا عندك صور أو مقاطع أرسلها، وإذا خلصت ارجع لـ Claude وقل «سو الفيديو».",
    "voice_replaced": "وصل الصوت الجديد ✅ وشلت القديم.\nالمدة: {dur}",
    "image": "وصلت الصورة ✅\nعندي الحين {c}.",
    "clip": "وصل المقطع ✅\nالمدة: {dur}\nعندي الحين {c}.",
    "note": "سجلت ملاحظتك 📝 بتوصل لـ Claude مع الملفات.",
    "new": "تمام، بدأنا فيديو جديد 🆕\nأرسل الصوت.",
    "empty": "للحين ما استلمت شي. أرسل صوت ElevenLabs أول.",
    "private": "هذا بوت خاص 🔒",
    "unknown": "أرسل صوت أو صورة أو مقطع، أو اكتب /start",
}


def call(method, files=None, **p):
    for attempt in range(3):
        try:
            if files:
                r = requests.post(API + method, data=p, files=files, timeout=60)
            else:
                r = requests.post(API + method, json=p, timeout=60)
            return r.json()
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return {}


def fmt(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def count(n, one, two, few, many):
    """Arabic counting: صورة وحدة، صورتين، 3 صور، 11 صورة."""
    if n == 1:
        return one
    if n == 2:
        return two
    return f"{n} {few if 3 <= n <= 10 else many}"


def empty_state():
    return {"voice": None, "images": [], "clips": [], "notes": [], "started": int(time.time())}


def load_state():
    pin = call("getChat", chat_id=OWNER).get("result", {}).get("pinned_message", {})
    doc = pin.get("document") or {}
    if doc.get("file_name") == "assets.json":
        path = call("getFile", file_id=doc["file_id"]).get("result", {}).get("file_path")
        if path:
            try:
                s = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{path}", timeout=30).json()
                s["_pin"] = pin["message_id"]
                return s
            except ValueError:
                pass
    return empty_state()


def save_state(s):
    """Send a fresh assets.json, pin it silently, and delete the previous one."""
    old = s.pop("_pin", None)
    body = json.dumps(s, ensure_ascii=False, indent=1).encode()
    caption = f"📦 ملفات الفيديو الحالي\nصوت: {'✅' if s['voice'] else '—'} · صور: {len(s['images'])} · مقاطع: {len(s['clips'])}"
    r = call("sendDocument", files={"document": ("assets.json", io.BytesIO(body), "application/json")},
             chat_id=OWNER, caption=caption, disable_notification="true")
    mid = r.get("result", {}).get("message_id")
    if mid:
        call("pinChatMessage", chat_id=OWNER, message_id=mid, disable_notification=True)
        if old:
            call("deleteMessage", chat_id=OWNER, message_id=old)
        s["_pin"] = mid


def summary(s):
    if not (s["voice"] or s["images"] or s["clips"] or s["notes"]):
        return MSG["empty"]
    lines = ["📋 اللي عندي للفيديو الحالي:"]
    lines.append(f"الصوت: {fmt(s['voice']['duration'])}" if s["voice"] else "الصوت: ما وصل")
    lines.append(f"الصور: {len(s['images'])}")
    lines.append(f"المقاطع: {len(s['clips'])}")
    if s["notes"]:
        lines.append(f"الملاحظات: {len(s['notes'])}")
    return "\n".join(lines)


def handle(m, s):
    chat = m["chat"]["id"]
    reply = lambda text: call("sendMessage", chat_id=chat, text=text, reply_to_message_id=m["message_id"])
    if m.get("from", {}).get("id") != OWNER:
        return reply(MSG["private"])

    text = (m.get("text") or "").strip()
    if text.startswith("/start"):
        return reply(MSG["start"])
    if text.startswith("/new"):
        pin = s.get("_pin")
        s.clear(); s.update(empty_state(), _pin=pin); save_state(s)
        return reply(MSG["new"])
    if text.startswith("/list"):
        return reply(summary(s))

    doc = m.get("document") or {}
    mime = doc.get("mime_type", "")
    audio = m.get("voice") or m.get("audio") or (doc if mime.startswith("audio/") else None)
    if audio:
        had = s["voice"] is not None
        s["voice"] = {"file_id": audio["file_id"], "duration": audio.get("duration", 0),
                      "name": audio.get("file_name", "voice"), "mime": audio.get("mime_type", "")}
        save_state(s)
        return reply(MSG["voice_replaced" if had else "voice"].format(dur=fmt(audio.get("duration"))))

    if m.get("photo") or mime.startswith("image/"):
        f = m["photo"][-1] if m.get("photo") else doc
        s["images"].append({"file_id": f["file_id"], "name": doc.get("file_name", f"image{len(s['images']) + 1}.jpg"),
                            "caption": m.get("caption", "")})
        save_state(s)
        n = len(s["images"])
        return reply(MSG["image"].format(c=count(n, "صورة وحدة", "صورتين", "صور", "صورة")))

    vid = m.get("video") or m.get("animation") or (doc if mime.startswith("video/") else None)
    if vid:
        s["clips"].append({"file_id": vid["file_id"], "duration": vid.get("duration", 0),
                           "name": vid.get("file_name", f"clip{len(s['clips']) + 1}.mp4"), "caption": m.get("caption", "")})
        save_state(s)
        n = len(s["clips"])
        return reply(MSG["clip"].format(dur=fmt(vid.get("duration")), c=count(n, "مقطع واحد", "مقطعين", "مقاطع", "مقطع")))

    if text:
        s["notes"].append(text)
        save_state(s)
        return reply(MSG["note"])
    return reply(MSG["unknown"])


def main():
    call("deleteWebhook")
    call("setMyCommands", commands=[
        {"command": "start", "description": "طريقة الشغل"},
        {"command": "new", "description": "فيديو جديد"},
        {"command": "list", "description": "وش استلمت"},
    ])
    call("setMyDescription", description="بوت الرندر حق تركي: أرسل الصوت والصور، ويرجع لك الفيديو جاهز.")
    s = load_state()
    offset = None
    print("bot running", flush=True)
    while True:
        r = call("getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            if "message" in u:
                try:
                    handle(u["message"], s)
                except Exception as e:  # keep the bot alive on any single bad message
                    print("error:", e, flush=True)
        if not r.get("ok"):
            time.sleep(3)


if __name__ == "__main__":
    main()
