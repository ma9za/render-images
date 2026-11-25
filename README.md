# render-images

Ready-made Runpod Serverless containers for Turki's videos. GitHub Actions builds them on every push to `main` and publishes to GHCR.

| Image | Use | Hardware |
|---|---|---|
| `ghcr.io/ma9za/render-motion:latest` | HTML motion (`seek(t)` + `window.READY`) → MP4, parallel browsers, Kufam font built in | CPU 32 vCPU |
| `ghcr.io/ma9za/render-blender:latest` | Blender 4.5 LTS, EEVEE on GPU → MP4 or transparent WebM | GPU (4090) |

Both send the result to Telegram through the bot whose token lives in the Runpod secret `BOTS` (env `BOT_TOKEN`, plus `CHAT_ID`).

Input fields are documented at the top of each `handler.py`.

## The bot (@Codexmabot)

Receives the voice, images, clips and notes for the next video and keeps the list as a pinned `assets.json` in the chat (no paid storage). Run it on any small server:

```
docker run -d --name render-bot --restart always -e BOT_TOKEN=YOUR_TOKEN ghcr.io/ma9za/render-bot:latest
```
