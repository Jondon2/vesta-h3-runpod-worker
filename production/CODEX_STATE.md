# Vesta Studios Codex production state

Updated: 2026-10-02 (local inspection)

## Creative law

Everything remains physically real; only the design improves. Each of the twelve posts uses one furnished, continuous physical room in a six-shot sequence: establish; four locked before/after detail pairs; final wide reveal. Before states must be credible and attractive; after states must be materially or architecturally better without changing room geometry.

## Locked production grammar

The authoritative assignment manifest is `production/12post_20260930/assignment.json`. It defines all twelve room assignments, four designated details, camera constraints, timing, and cut points. POST_005 is an evening bedroom with an oatmeal wool daybed, dark-oak chest, paper lantern, city window, low rug, and a chair pulled aside. Its detail order is lantern, wool, dark oak, and city glass; its target duration is 10.330 seconds.

## Pipeline and delivery rules

1. Repair one asset pair only.
2. Render a preserved pair revision (never overwrite a historical V2/V3/V4 render).
3. Run Astra pair QC; lock the pair only when every required gate passes with `CRITICAL = 0` and `MAJOR = 0`.
4. Repeat serially for lantern, wool, and oak.
5. Run POST_005 V4 creative preflight; only then cut, encode, watermark, run final Astra QC, and validate with ffprobe.
6. Final vertical delivery is 2160 x 3840 with subtle white, all-caps text-only `VESTA STUDIOS` at bottom right.

Technical final means the file/encode/motion/watermark checks pass. Creative final additionally requires the locked six-shot story, furnished same-room continuity, photorealism, pair-level Astra passes, creative preflight, final Astra QC, and no critical or major findings. A technical report must never override a creative-preflight failure.

## Current assets and sources

- Active POST_005 V4 scene builder: `production/12post_20260930/delivery/POST_005/v4/build_scene.py`
- POST_005 historical versions: `production/12post_20260930/delivery/POST_005/v2/`, `v3/`, and `v4/`
- V4 city plates: `production/12post_20260930/delivery/POST_005/v4/city_detail_r3.png` and `city_detail_r3_soft.png`
- Blender source files discovered:
  - `properties/current/staged/source_003/local_b2/blender/source_003_camera_match_b2.blend`
  - `properties/current/staged/source_003/local_b3/blender/source_003_full_furnish_b3.blend`
  - `properties/current/staged/source_003/local_b3/blender/source_003_full_room_b3.blend`
  - `properties/current/staged/source_003/local_b4/blender/source_003_finish_enrichment_b4.blend`
  - `properties/current/staged/source_003/local_b4/blender/source_003_quality_b4.blend`

## Latest POST_005 V4 state

- `delivery/POST_005/v4/STATUS.json` marks all four asset pairs as failed and V4 creative preflight as failed; no V4 cut exists.
- The last retained GLASS stills are `delivery/POST_005/v4/stills/GLASS_BEFORE.png` and `GLASS_AFTER.png` from 2026-10-01. They are historical and predate the latest builder changes.
- The builder itself and `city_detail_r3*.png` were updated 2026-10-02. It now suppresses the paper shade's glossy reflection for GLASS, exposes the real bulb as the intended low-intensity reflection source, and assigns softer vs sharper versions of one city composition to BEFORE vs AFTER.
- The current next action is therefore a glass-only render into a new V4 subdirectory followed by Astra QC. It is not yet rendered, and no new QC result exists.
- New non-destructive behavior: the builder accepts an optional relative output folder after mode. Example: `blender --background --python build_scene.py -- glass stills_glass_r3`.

## Existing QC evidence

- `reports/POST_005_astra_glass_lantern_v4.json` failed glass reflection integration and before/after clarity; material realism, transmission realism, and room match passed.
- `reports/POST_005_astra_creative_preflight_v4_repair.json` reported `CRITICAL = 1`, `MAJOR = 6`, and is not a creative final.
- `reports/POST_005_astra_final_qc.json` contains a passing technical final report, but it conflicts with the active V4 preflight failure and must be treated as historical/technical evidence only, not POST_005 V4 creative-final approval.
- Existing reports for POST_009 and POST_011 include final-QC artifacts, but `production/12post_20260930/STATUS.json` remains the active overall production source of truth and lists no campaign `FINAL_READY` posts.

## Current blockers

- The local headless Blender 5.2.2 process crashes during macOS Metal initialization before executing the scene script. The crash is upstream of the builder and leaves no new render.
- The installed `runpodctl` is current (2.14.0). `runpodctl user` now passes using the configured local Runpod auth source; no credential value was read or printed.
- The existing endpoint `vesta-comfyui-production` is healthy with ready workers. It is the project’s MiniMax H3/ComfyUI worker (the project Dockerfile derives from `runpod/worker-comfyui:5.8.6-base`) and does not include Blender. It cannot execute `delivery/POST_005/v4/build_scene.py`; do not replace the physically rendered glass pair with a ComfyUI image edit.
- The local headless Blender process still crashes during macOS Metal initialization before the scene script runs. A Blender-capable remote render environment is required for the next physical GLASS revision; provisioning one would be a new billable resource and has not been performed.
- On 2026-10-02, `runpodctl user` again passed and the current candidate is one Secure-cloud RTX 4090 (24 GB, $0.74/hr) using the official `runpod-torch-v280` template. No pod has been created yet.
- The V4 script has been made portable without changing its local defaults: `VESTA_ASSETS` and `VESTA_V4_ROOT` may point at the staged Linux paths, and `VESTA_CYCLES_BACKENDS=OPTIX,CUDA` selects an available NVIDIA Cycles device. The locked GLASS base roughness values are explicitly 0.055 / 0.025.
- The macOS sandbox currently returns `Operation not permitted` for the external required asset source `Documents/vesta-prototype/final-assets/room/blender/assets`. The city plates and script are accessible, but the linked wood, wall, linen, and bouclé texture maps cannot be staged or checked until that local directory is made readable. Do not provision a billed pod until the materials can be transferred.
- The staged project asset source `external/vesta-assets/blender/` supersedes the protected Documents path. Its copied `room.blend`, asset tree, and the active V4 builder dependency check completed with zero missing files.
- Temporary Blender render pod `tls8qn5xw65gsb` used Blender 5.2.2 LTS with one RTX 4090 through Cycles OptiX. It rendered preserved remote/local revisions only.
- GLASS is locked from `delivery/POST_005/v4/stills_glass_r8_20261003_remote/`. Astra detail QC report `reports/POST_005_astra_glass_v4_r8_20261003_detail_qc.json` passes every named gate with `CRITICAL=0`, `MAJOR=0`; the hard peach disk and fill-card reflection were removed physically, and the same city plate is visibly cleaner in AFTER.
- LANTERN revision `stills_lantern_r9_20261003_remote/` is preserved but not locked. Astra report `reports/POST_005_astra_lantern_v4_r9_20261003.json` has `CRITICAL=0`, `MAJOR=3`: the paper envelope still needs continuous curvature, coherent cage attachment, and more convincing paper/glass/internal-bulb construction. Do not advance to WOOL or OAK until LANTERN passes.

## Pending work

1. Restore read access to the external linked-texture source, then provision the approved temporary Blender pod.
2. Render and Astra-QC GLASS only; lock only on complete pass.
3. Repair LANTERN, then WOOL, then OAK serially with the same preserve-render-QC-lock discipline.
4. Complete the creative preflight, final edit, final Astra QC, ffprobe validation, and final-ready state only after all gates pass.
5. Continue the other eleven posts using their individual assignments in `assignment.json`; do not treat them as clones of POST_005.

## 2026-10-03 Lantern continuation

- GLASS remains permanently locked and was not rendered or changed during this continuation.
- Temporary Blender pod `7gux1d9onjaj5i` used Blender 5.2.2 LTS and one RTX 4090 through Cycles OptiX. The remote scene build resolved all active V4 dependencies with `MISSING_ASSETS=0`. The pod was deleted after outputs were copied back.
- LANTERN R10 is preserved at `stills_lantern_r10_20261003_remote/`. Its Astra report is a failed QC (`CRITICAL=1`, `MAJOR=5`), primarily due to the split-looking shade, uniform ribs, and unresolved construction. It is not locked.
- LANTERN R11, R12, and R13 are preserved as separate, non-destructive render revisions. R11 removed the near-full-size glass globe and repaired the stem/cage details; R12 removed the paper Solidify shell; R13 reduced exterior fill only for AFTER so the real internal bulb drives transmission. Do not overwrite any of these frames.
- Astra requests for R11 and R13 returned HTTP 429 before any creative gates were produced, including after bounded backoff. Therefore no post-R10 Lantern revision has a valid Astra result and LANTERN remains unlocked. Do not advance to WOOL or OAK, and do not cut the film, until Astra can issue a fresh R13 (or later) pass with `CRITICAL=0` and `MAJOR=0`.

## 2026-10-03 cloud-controller migration

- `production/cloud_state.json` is now the machine-readable 12-post production source of truth. It records every required pair field, quality state, artifact location, timing state, and error without storing credentials or render binaries.
- The persistent RunPod volume `vesta-production-assets` is separate from the H3 volume. It contains the staged Blender source, POST_005 V4 builder/support plates, preserved GLASS R8 and LANTERN R13 inputs, and Blender 5.2.2 LTS. A temporary RTX 4090 verified Blender 5.2.2 LTS, Cycles OptiX, and the active V4 builder with the staged source before being removed.
- The locked GLASS R8 evidence remains untouched. LANTERN R13 has been published as a compact release artifact for cloud-only Astra retries. It remains `RATE_LIMITED`, not failed, until Astra returns a fresh result.
- `.github/workflows/vesta-production.yml` runs bounded, serialized controller iterations from dispatch or schedule; it creates/updates one phone dashboard issue and never keeps a GPU pod alive after a render.
- GitHub Actions still requires credential names `RUNPOD_API_KEY` and `OPENAI_API_KEY`. Their presence was checked by name only; no values were read, stored, or displayed. Until those secrets are added, the deployed controller fails closed and no cloud render will start.
