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
