# render-images

Ready-made Runpod Serverless containers for Turki's videos. GitHub Actions builds them on every push to `main` and publishes to GHCR.

| Image | Use | Hardware |
|---|---|---|
| `ghcr.io/ma9za/render-motion:latest` | HTML motion (`seek(t)` + `window.READY`) → MP4, parallel browsers, Kufam font built in | CPU 32 vCPU |
| `ghcr.io/ma9za/render-blender:latest` | Blender 4.5 LTS, EEVEE on GPU → MP4 or transparent WebM | GPU (4090) |

Both send the result to Telegram through the bot whose token lives in the Runpod secret `BOTS` (env `BOT_TOKEN`, plus `CHAT_ID`).

Input fields are documented at the top of each `handler.py`.

## The bot (@Codexmabot)

Runs on Telegram's serverless platform (tgcloud), no server. Source in `tgcloud-bot/`.
It stores the current video's voice, images, clips and notes in its database; `endpoints/assets` (owner only) lists them or returns one file as base64.

Deploy: `cd tgcloud-bot && npm i && TGCLOUD_TOKEN=... NODE_USE_ENV_PROXY=1 npx tgcloud push` (then `npx tgcloud migrate` after schema changes).
