FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl fontconfig fonts-noto-core fonts-noto-color-emoji \
 && pip install --no-cache-dir playwright==1.49.0 runpod requests \
 && playwright install --with-deps chromium \
 && mkdir -p /usr/share/fonts/truetype/turki \
 && curl -fsSL -o "/usr/share/fonts/truetype/turki/Kufam[wght].ttf" "https://github.com/google/fonts/raw/main/ofl/kufam/Kufam%5Bwght%5D.ttf" \
 && fc-cache -f \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY motion/handler.py /app/handler.py
WORKDIR /app
CMD ["python", "-u", "/app/handler.py"]
