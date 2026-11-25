# GPU worker: Blender 4.5 (EEVEE) + Chromium with hardware WebGL for three.js motion.
FROM nvidia/cuda:12.6.3-base-ubuntu24.04

ARG BLENDER_VER=4.5.3
ARG BLENDER_SERIES=4.5
ENV PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive \
    NVIDIA_DRIVER_CAPABILITIES=all NVIDIA_VISIBLE_DEVICES=all \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PIP_BREAK_SYSTEM_PACKAGES=1 \
    CHROME_GL_ARGS='["--use-angle=vulkan", "--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan", "--disable-vulkan-surface", "--enable-unsafe-webgpu"]'

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip ffmpeg curl xz-utils ca-certificates \
      libegl1 libgl1 libglvnd0 libgles2 libvulkan1 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 \
      libsm6 libice6 libx11-6 libxext6 libxcursor1 libxinerama1 libxrandr2 libwayland-client0 libdbus-1-3 \
      fontconfig fonts-noto-core fonts-noto-color-emoji \
 && mkdir -p /opt/blender \
 && curl -fsSL "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VER}-linux-x64.tar.xz" \
      | tar -xJ -C /opt/blender --strip-components=1 \
 && pip3 install --no-cache-dir runpod requests playwright==1.49.0 \
 && playwright install --with-deps chromium \
 && mkdir -p /usr/share/glvnd/egl_vendor.d /usr/share/vulkan/icd.d /usr/share/fonts/truetype/turki \
 && printf '{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}' > /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
 && printf '{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0","api_version":"1.3"}}' > /usr/share/vulkan/icd.d/nvidia_icd.json \
 && curl -fsSL -o "/usr/share/fonts/truetype/turki/Kufam[wght].ttf" "https://github.com/google/fonts/raw/main/ofl/kufam/Kufam%5Bwght%5D.ttf" \
 && fc-cache -f \
 && apt-get purge -y curl xz-utils && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY blender/handler.py /app/handler.py
COPY motion/handler.py /app/motion_handler.py
WORKDIR /app
CMD ["python3", "-u", "/app/handler.py"]
