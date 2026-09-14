# Vesta H3 RunPod Worker

RunPod Serverless + ComfyUI worker for MiniMax H3 video generation for Vesta.

This repository is being configured for:
- RunPod Serverless
- ComfyUI native MiniMax H3 nodes
- MiniMax H3 text-to-video and image-to-video
- Vesta Visual Director / Astra orchestration
- Native video + audio output

## Important GPU note

The full native H3 stack is much heavier than a standard 16 GB ComfyUI workload. A 48 GB GPU is the practical minimum target for 768p with offloading; 80 GB is the safer target for production reliability. The repository keeps the model weights separate from source code and provides an automated image-build path so the worker can be deployed repeatedly without manual node installation.

## Planned container

Base image: `runpod/worker-comfyui:5.8.6-base`

ComfyUI: pinned to a release with native MiniMax H3 support.

Model files used by the initial workflow:
- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

The first production workflow will support T2V and first-frame/last-frame I2V. Reference-to-video can be added later as a separate heavier model.

## Production package

- Spec: [`docs/vesta-production-spec.md`](docs/vesta-production-spec.md)
- Shot presets: [`config/vesta_shot_presets.json`](config/vesta_shot_presets.json)
- Astra QC: [`config/astra_qc_categories.json`](config/astra_qc_categories.json)
- H3 templates: [`workflows/`](workflows/) (10s, 15s, 20s pair, FL2VA, 4K SeedVR2)
- Container: `ghcr.io/jondon2/vesta-h3-runpod-worker:runtime-v5` (rollback: `runtime-v4`, then `runtime-v3`)

Do not use 5-second / 124-frame clips as a production standard. Native generate at 768 short-edge; deliver 4K after selection.

Persistence:
- Inputs: `/runpod-volume/input` is ComfyUI's real input root → `LoadImage` `<file>` (last frames `last_frames/<file>`; SeedVR2 `vesta_renders/<file>`)
- Outputs: `/runpod-volume/output/vesta` → `SaveVideo` prefix `vesta/`
- Never compressed MCP base64 for originals or production MP4s.
