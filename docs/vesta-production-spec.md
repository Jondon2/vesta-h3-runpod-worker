# Vesta MiniMax H3 production spec

Status: **prepared, not executed.** No GPU worker and no paid generation from this package.

Endpoint `vesta-comfyui-production` (`f4xegabv7ij4ob`) stays parked: `minWorkers=0`, `maxWorkers=0`, FlashBoot OFF.

This spec turns the completed H3 tests into a reusable production system. The 124-frame / ~5.17 s I2V job (`f063efc7-fb81-4c81-982a-5f9d92b80419-u1`) proved the worker, models, sampler, and I2V graph. It is **not** a Vesta production duration.

## 1. What the benchmark proved

| Item | Result |
|---|---|
| Worker image (rollback) | `ghcr.io/jondon2/vesta-h3-runpod-worker:runtime-v3` |
| Worker image (this package) | `ghcr.io/jondon2/vesta-h3-runpod-worker:runtime-v4` |
| Volume | `vesta-h3-models` (`34m0r6jazp`) at `/runpod-volume` |
| GPU | 1× NVIDIA RTX 6000 Ada 48 GB, US-IL-1, `$1.75/hr` |
| I2V 1152×768, 124 frames, 20 steps, video only | COMPLETED in 599,687 ms |
| Output | `Vesta_H3_i2v124_00001_.mp4`, 1152×768, 124 frames @ 24 fps, 5.167 s |
| MCP `run-endpoint` | Workflow-only JSON (~2 KB) submits. Original JPEG base64 (~279k chars) does not. |

Do not use 5-second / 124-frame clips as a production standard.

## 2. Duration policy

H3 `length` is frame count at 24 fps, snapped to the **17k+5** grid. Trained range is about 124–362 frames.

| Tier | Target | `length` | Duration | How |
|---|---|---|---|---|
| Not production | ~5 s | 124 | 5.17 s | Benchmark only |
| Standard | ~10 s | **243** | 10.13 s | One I2V generation |
| Premium | ~15 s | **362** | 15.08 s | One I2V generation |
| Campaign | ~20 s | **243 + 243** | ~20.3 s | Two connected 10 s shots |

Never generate a single 481-frame (~20 s) take on this 48 GB endpoint. Campaign length is two 10 s shots with Shot B `first_frame` = last decoded frame of Shot A.

## 3. Native canvas vs 4K delivery

**Generate** at H3-friendly short-edge 768. **Never** native 4K.

| Aspect | Generate | 4K delivery |
|---|---|---|
| 16:9 | 1344×768 | 3840×2160 (cover-scale 2.857×, center-crop height 2194→2160) |
| 3:2 interiors | 1152×768 | 3840×2560 (or 3240×2160 on a 16:9 timeline) |
| 9:16 | 768×1344 | 2160×3840 |
| 1:1 | 768×768 | 2160×2160 |

Sampler defaults (all production presets): **20 steps**, `res_multistep`, `simple`, fps **24**, video only in-model.

## 4. Full-resolution input architecture

The benchmark still was 1024×682 (209,373 bytes). Cursor MCP `run-endpoint` could not carry that JPEG as `input.images[].image` base64; the submitted job used a 512×341 JPEG of the same photo. That is **not** allowed in production.

The official `runpod/worker-comfyui` handler only accepts extra stills as in-payload base64 (`upload_images` → Comfy `/upload/image`). That is the path we are replacing.

### Production path (required)

1. Stage the **original** listing still on network volume `34m0r6jazp`:
   - `/runpod-volume/input/<listing_id>.<jpg|png|webp>`
2. `vesta_start.sh` creates:
   - `/comfyui/input/volume` → `/runpod-volume/input`
   - `/comfyui/input/last_frames` → `/runpod-volume/last_frames`
   - `/comfyui/input/vesta_renders` → `/runpod-volume/output/vesta` (LoadVideo alias)
   - `/comfyui/output/vesta` → `/runpod-volume/output/vesta` (SaveVideo only)
3. Workflow `LoadImage` uses `volume/<listing_id>.jpg` (and `last_frames/<id>.png` when needed).
4. Job payload is **workflow JSON only**. No `images` array. MCP-sized. Original pixels unchanged.
5. Production `SaveVideo` prefixes are `vesta/...` so files land on the volume. The worker wrapper does **not** base64 those files back through MCP.

Staging onto the volume (no GPU worker required):

- **Preferred:** attach `34m0r6jazp` to a **CPU** pod or use the volume’s S3-compatible API / console file upload, then write `input/`.
- **Alternate:** signed HTTPS URL in object storage (R2/S3). A future handler download (`input.image_url` → `/comfyui/input/volume/…`) keeps the job small. Not in `runtime-v3` yet; do not send the URL through MCP as a giant base64 field.
- **Do not:** compress, downscale, or base64 the original through Cursor MCP `run-endpoint`.

Do not symlink the entire `/comfyui/output` tree to the volume. worker-comfyui 5.8.6 resolves history via Comfy `/view` under `/comfyui/output`; replacing that directory would mix volume files with handler temp/history and can break fetches. Only the `vesta/` subfolder is persistent.

### Production output path (required)

| Role | Path |
|---|---|
| Volume (source of truth) | `/runpod-volume/output/vesta/<file>.mp4` |
| Comfy SaveVideo | `/comfyui/output/vesta/` → volume (symlink) |
| SeedVR2 LoadVideo | `vesta_renders/<file>.mp4` → same volume dir |
| Job result | `{ "type": "volume", "path": "/runpod-volume/output/vesta/..." }` — not base64 |

Campaign 20 s delivery is two native MP4s concatenated with `scripts/concat_campaign.sh` (ffmpeg concat demuxer, CPU). Retrieve files from the volume (CPU pod, console, or S3 API), not from the MCP job payload.

## 5. Shot presets

Source of truth: [`config/vesta_shot_presets.json`](../config/vesta_shot_presets.json).

| ID | Name | Duration | Frames | Notes |
|---|---|---|---|---|
| `hero-push-in` | Hero Push-In | 10 s | 243 | Default listing move |
| `lateral-parallax` | Lateral Parallax | 10 s | 243 | Slider / wall-parallel |
| `lounge-arc` | Lounge Arc | 10 s | 243 | Orbit seating group |
| `doorway-reveal` | Doorway Reveal | 10 s | 243 | Prefer FL2VA last_frame |
| `wide-establishing-reveal` | Wide Establishing Reveal | 10 s | 243 | Beat 1 of a listing |
| `detail-glide` | Detail Glide | 10 s | 243 | Hero/focus beat |
| `foreground-pass` | Foreground Pass | 10 s | 243 | Occlusion parallax |
| `campaign-pair` | Campaign Pair | 20 s | 243+243 | Two-shot sequence |
| `premium-15` | Premium 15 | 15 s | 362 | Validate 1344×768 before 1152×768 |

Every preset includes: camera prompt, geometry-lock prompt, ending instructions, resolution rules, use case, output structure.

Prompt assembly for Astra:

```
{scene_description}

{camera_prompt}

{geometry_lock_prompt}

{ending_instructions}
```

## 6. Four-beat listing template

| Beat | 10 s one-shot | 15 s one-shot | 20 s two-shot |
|---|---|---|---|
| Establishing | 0–2.5 s | 0–3.5 s | Shot A first half |
| Interactive move | 2.5–7.5 s | 3.5–11 s | Shot A remainder |
| Hero / focus | 7.5–9.2 s | 11–13.5 s | Shot B from last frame of A |
| Ending / slate | 9.2–10.1 s | 13.5–15.1 s | Shot B last_frame + post |

## 7. Workflow templates (do not execute)

| File | Mode |
|---|---|
| [`workflows/i2v_10s.json`](../workflows/i2v_10s.json) | Standard 243-frame I2V, first_frame only |
| [`workflows/i2v_15s.json`](../workflows/i2v_15s.json) | Premium 362-frame I2V, first_frame only |
| [`workflows/i2v_20s_shot_a.json`](../workflows/i2v_20s_shot_a.json) | Campaign Shot A (243, hold ending) |
| [`workflows/i2v_20s_shot_b.json`](../workflows/i2v_20s_shot_b.json) | Campaign Shot B (243, first=last of A) |
| [`workflows/i2v_fl2va.json`](../workflows/i2v_fl2va.json) | first_frame + last_frame pathing |
| [`workflows/upscale_4k_seedvr2.json`](../workflows/upscale_4k_seedvr2.json) | Post-selection 4K finishing |

Submit shape (when later approved):

```json
{
  "input": {
    "workflow": { }
  }
}
```

No `images` key. `LoadImage` names must already exist on the volume.

`MiniMaxH3ImageToVideo` stretches `first_frame` to the canvas and cover-crops `last_frame`. The last still must match room geometry in the first still.

## 8. 4K finishing architecture

H3 max useful canvas is ~768 short-edge. 4K is **after** human/Astra selection, not on every queued job.

**Recommended upscaler: SeedVR2** — **native ComfyUI v0.30.1** (`comfy_extras/nodes_seedvr.py` / PR #14424). Do **not** install `numz/ComfyUI-SeedVR2_VideoUpscaler`. The old template names `SeedVR2LoadModel` / `SeedVR2VideoUpscale` are wrong for this runtime.

Why SeedVR2 over per-frame RealESRGAN:

- Temporal batching (batch size **4n+1**, minimum 5) keeps architecture edges and furniture textures stable across frames.
- Conservative restoration: less hallucinated millwork than a 4× photo upscaler.
- One-step diffusion: cheaper than a multi-step video model at 243–362 frames.

Production settings (template only — **do not download or run** in this pass):

| Item | Value |
|---|---|
| Package | ComfyUI core `comfy_extras/nodes_seedvr.py` at tag **v0.30.1** |
| Nodes | `UNETLoader`, `VAELoader`, `LoadVideo`, `GetVideoComponents`, `ImageScale`, `SeedVR2Preprocess`, `VAEEncodeTiled`, `SeedVR2TemporalChunk`, `SeedVR2Conditioning`, `KSampler` (1 step, euler/simple), `SeedVR2TemporalMerge`, `VAEDecodeTiled`, `SeedVR2PostProcessing` (`lab`), `CreateVideo`, `SaveVideo` |
| Source | Hugging Face [`Comfy-Org/SeedVR2`](https://huggingface.co/Comfy-Org/SeedVR2) |
| UNET | `seedvr2_3b_int8_convrot.safetensors` — **3,458,259,704 bytes** (~3.22 GiB), SHA256 `c3dec8bcc5916843a8a858572970597462e1f2dc598d6dfd818f6cd40f53a157` |
| VAE | `seedvr2_ema_vae_fp16.safetensors` — **501,324,814 bytes** (~478 MiB); same blob as `ema_vae_fp16.safetensors` |
| Volume paths | `/runpod-volume/models/diffusion_models/` and `/runpod-volume/models/vae/` via `extra_model_paths.yaml` |
| Target 16:9 | `ImageScale` lanczos to **3840×2160**, crop center |
| Sampler | 1 step, `euler` / `simple`, cfg 1, denoise 1, seed 1 |
| Temporal | `SeedVR2TemporalChunk` `chunking_mode=auto` (4n+1 internally) |
| Frame interp | **off** |
| H3 unload | **Required.** H3 I2V peaked at **33,888 MB**. Same 48 GB Ada cannot hold H3 + SeedVR2. Run 4K as a **separate job** that does not load H3 nodes (idle timeout 5 s with min=0 cold-starts a clean worker). Typical 3B INT8 4K after unload: ~10–20 GB. |
| 7B | `seedvr2_7b_int8_convrot.safetensors` is **8,334,897,976 bytes**. Not the production default on this card. |

`VESTA_DOWNLOAD_SEEDVR2` defaults to **0**. Do not pull these weights until an approved 4K pass.

Fallback if SeedVR2 weights are absent: tiled RealESRGAN / Nomos per frame + Lanczos. Inferior flicker; only a stopgap.

Post overlays (fade, end-card type, CTA, QR) apply **after** 4K so branding stays sharp.

## 9. Cost and VRAM (estimates)

Anchor: measured I2V 1152×768 / 124f / 20 steps = 599.7 s ≈ **$0.29** job-only at $1.75/hr. A duplicate idle worker has appeared at `maxWorkers=1`; treat **~2×** as the pessimistic GPU bill.

| Mode | Est. runtime | Job-only | Extra-worker case | VRAM |
|---|---|---|---|---|
| 10 s 243f | ~20 min | ~$0.57 | ~$1.14 | Unproven at 1152×768; expect tight 40–48 GB |
| 15 s 362f | ~29 min | ~$0.85 | ~$1.70 | High OOM risk at 1152×768; validate 1344×768 first |
| 20 s two-shot | ~41 min | ~$1.17 | ~$2.34 | Each shot = 10 s |
| 4K SeedVR2 (10 s) | ~6 min est. | ~$0.18 | n/a if H3 unloaded | ~10–20 GB typical |

OOM → park `maxWorkers=0`, do not retry on a bigger GPU without approval.

## 10. Astra QC

Categories: [`config/astra_qc_categories.json`](../config/astra_qc_categories.json).

Fail the shot (do not upscale, do not ship) on morphing, duplicated objects, geometry drift, or a broken ending. Taste/luxury is scored, not auto-failed, unless it is clearly non-listing.

## 11. Operating rules

1. `minWorkers=0`. `maxWorkers=1` only while an approved job is in flight, then **0**.
2. FlashBoot OFF until policy changes.
3. One production generation at a time. No automatic retry.
4. `list-endpoint-workers` is authoritative if `/health` disagrees.
5. Do not raise `maxWorkers` if a second worker appears (known incident).
6. 4K and overlays only on the selected clip.
