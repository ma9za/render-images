FROM nvidia/cuda:12.4.1-base-ubuntu22.04

ARG BLENDER_VER=4.5.3
ARG BLENDER_SERIES=4.5
ENV PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive \
    NVIDIA_DRIVER_CAPABILITIES=all NVIDIA_VISIBLE_DEVICES=all

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip ffmpeg curl xz-utils ca-certificates \
      libegl1 libgl1 libglvnd0 libgles2 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 \
      libsm6 libice6 libx11-6 libxext6 libxcursor1 libxinerama1 libxrandr2 libwayland-client0 libdbus-1-3 \
      fontconfig fonts-noto-core \
 && mkdir -p /opt/blender \
 && curl -fsSL "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VER}-linux-x64.tar.xz" \
      | tar -xJ -C /opt/blender --strip-components=1 \
 && pip3 install --no-cache-dir runpod requests \
 && mkdir -p /usr/share/glvnd/egl_vendor.d \
 && printf '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' > /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
 && apt-get purge -y curl xz-utils && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY handler.py /app/handler.py
WORKDIR /app
CMD ["python3", "-u", "/app/handler.py"]
