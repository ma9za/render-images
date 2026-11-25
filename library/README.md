# 3D library

Reusable models for motion videos. Each model is loaded with `model(url, length, {fwd})` in the page: scaled to a length, base on the ground, nose turned to +z, toon shading + black outline.

| File | What | Source | Forward | Notes |
|---|---|---|---|---|
| models/tanker.glb | Crude oil tanker (red hull) | Halai Tripo, from Turki's image | +x | Hormuz video, length 16 |
| models/destroyer.glb | Navy guided-missile destroyer | Halai Tripo, from Turki's image | +x | length 13 |
| models/jet.glb | Twin-engine carrier fighter jet | Halai Tripo, from Turki's image | +x | length 5 (x3–6 on maps) |

Free packs used alongside (CC0, no credit needed), fetched from `https://cdn.cinevva.com/assets/packs/<pack>/<file>.glb` with `<pack>/Textures/colormap.png`:
- kenney/city-kit-commercial (buildings, skyscrapers), kenney/city-kit-roads (barriers, cones)
- kenney/watercraft-pack (ship-cargo-a/b/c, boat-speed-a), forward -z
- kenney/car-kit, quaternius/ultimate-animated-characters

Drawn in code (see the Hormuz/Mukaab pages): naval mines, fire/smoke, mine blast, cube building, crane.

maps/hormuz.json: Natural Earth 50m countries around the Strait of Hormuz, Mercator, units ≈ map units (x east, y south). Rebuild or make new regions with maps/mkmap.mjs (world-atlas + d3-geo + polygon-clipping).
