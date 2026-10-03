# Vesta Studios production context

## Working rules

- The current local filesystem and Git state are authoritative. Preserve every historical output; never use `git reset`, `git clean`, destructive checkout, or overwrite prior render revisions.
- V2 and V3 are historical artifacts. POST_005 V4 is the active pilot. Do not create V5 unless V4 has a genuine architectural blocker.
- Create every repair render in a new, date- or revision-named directory beneath the current version. The POST_005 V4 builder accepts an optional relative output directory: `blender --background --python build_scene.py -- glass stills_glass_r3`.
- A technical pass (format, duration, encode, watermark, ffprobe, or motion) is not a creative final. A creative final additionally requires the locked six-shot room grammar, physical realism, same-room continuity, asset-pair gates, creative preflight, and final Astra QC with `CRITICAL = 0` and `MAJOR = 0`.

## Creative law and format

"Everything stays physically real. Only the design becomes better."

Each post is one fully furnished, coherent room:

1. furnished establishing shot;
2. detail 1 before to after;
3. detail 2 before to after;
4. detail 3 before to after;
5. detail 4 before to after;
6. final wide furnished reveal.

Detail-pair cameras and geometry remain locked; only the designated design/material state changes.

## Active checkpoint

- POST_005 V4 **GLASS is locked**. Preserve `stills_glass_r8_20261003_remote/` and its Astra detail report; do not render, modify, or reopen this pair unless a future verified regression is recorded.
- Scene builder: `production/12post_20260930/delivery/POST_005/v4/build_scene.py`.
- LANTERN R13 is the active candidate at `stills_lantern_r13_20261003_remote/`. Its frames are preserved and must be Astra-QC retried before another Lantern render is considered. HTTP 429 is `RATE_LIMITED`, never a creative failure and never a reason to rerender.
- WOOL and OAK have not started. Do not render either until LANTERN has a fresh Astra pass with `CRITICAL = 0` and `MAJOR = 0`.
- The cloud controller state is `production/cloud_state.json`. It is the operational source of truth for bounded GitHub Actions iterations and the phone dashboard.

## Primary controls

- 12-post assignment manifest: `production/12post_20260930/assignment.json`
- Production status: `production/12post_20260930/STATUS.json`
- Current handoff: `production/CODEX_STATE.md`
- Astra reports: `production/12post_20260930/reports/`
- POST_005 delivery history: `production/12post_20260930/delivery/POST_005/`
- Finalization helper: `production/12post_20260930/delivery/finish_post.sh`

## Execution constraints

- Do not cut POST_005 until every asset pair is locked: GLASS, LANTERN, WOOL, and OAK.
- Never set `*_FINAL_READY` while any creative gate reports a critical or major issue.
- All final vertical exports must be 2160 x 3840 with the text-only, subtle white `VESTA STUDIOS` watermark in the bottom right.
