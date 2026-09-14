#!/usr/bin/env bash
set -euo pipefail

# Prefer RunPod network volume so the ~42 GB H3 model set is downloaded once
# and reused across worker restarts. Fall back to the container model directory
# when no writable network volume is attached.
if [ -d /runpod-volume ] && [ -w /runpod-volume ]; then
  MODEL_ROOT="${VESTA_MODEL_ROOT:-/runpod-volume/models}"
  echo "Vesta: using persistent model root: ${MODEL_ROOT}"
else
  MODEL_ROOT="/comfyui/models"
  echo "Vesta: no writable network volume detected; using ephemeral ${MODEL_ROOT}"
fi

mkdir -p \
  "${MODEL_ROOT}/diffusion_models" \
  "${MODEL_ROOT}/text_encoders" \
  "${MODEL_ROOT}/vae" \
  "${MODEL_ROOT}/upscale_models"

# Full-resolution listing stills live on the network volume so job payloads
# stay small (workflow JSON only). Do not send original JPEGs as MCP/base64.
#
# ComfyUI v0.30.1 LoadImage/LoadVideo call exists_annotated_filepath, which
# rejects any path whose realpath escapes the input root (symlink jail).
# Do NOT ln -s volume input dirs into /comfyui/input. Instead make
# /runpod-volume/input ComfyUI's real --input-directory.
#
# worker-comfyui 5.8.6 /start.sh hardcodes:
#   python -u /comfyui/main.py --disable-auto-launch --disable-metadata ...
# It does not forward extra argv or an env var. Inject --input-directory
# into that launch line before exec /start.sh.
#
# Production videos persist under /runpod-volume/output/vesta. Do NOT replace
# /comfyui/output — worker-comfyui resolves history files via Comfy /view
# relative to that directory. A Vesta subfolder symlink keeps /view working
# while files land on the volume. That output symlink is not a LoadImage path.
if [ -d /runpod-volume ] && [ -w /runpod-volume ]; then
  mkdir -p \
    /runpod-volume/input \
    /runpod-volume/input/last_frames \
    /runpod-volume/input/vesta_renders \
    /runpod-volume/output/vesta
  mkdir -p /comfyui/input /comfyui/output

  # runtime-v4 leftover input aliases. Never leave these for LoadImage/LoadVideo.
  for leftover in /comfyui/input/volume /comfyui/input/last_frames /comfyui/input/vesta_renders; do
    if [ -L "${leftover}" ] || [ -e "${leftover}" ]; then
      rm -rf "${leftover}"
      echo "Vesta: removed leftover input mapping ${leftover}"
    fi
  done

  if [ ! -f /start.sh ]; then
    echo "Vesta: FATAL: /start.sh missing; cannot inject --input-directory" >&2
    exit 1
  fi
  if ! grep -q 'python -u /comfyui/main.py' /start.sh; then
    echo "Vesta: FATAL: /start.sh does not launch python -u /comfyui/main.py" >&2
    exit 1
  fi
  if ! grep -q -- '--input-directory /runpod-volume/input' /start.sh; then
    sed -i 's|python -u /comfyui/main.py|python -u /comfyui/main.py --input-directory /runpod-volume/input|g' /start.sh
  fi
  if ! grep -q -- '--input-directory /runpod-volume/input' /start.sh; then
    echo "Vesta: FATAL: failed to inject --input-directory into /start.sh" >&2
    exit 1
  fi

  if [ -e /comfyui/output/vesta ] && [ ! -L /comfyui/output/vesta ]; then
    echo "Vesta: moving leftover /comfyui/output/vesta aside (not a symlink)"
    mv /comfyui/output/vesta "/comfyui/output/vesta.ephemeral.$$"
  fi
  ln -sfn /runpod-volume/output/vesta /comfyui/output/vesta

  # Older runtime-v3 start script mapped the entire output tree. Remove it so
  # worker-comfyui temp/history files stay on local disk.
  if [ -L /comfyui/output/volume ]; then
    rm -f /comfyui/output/volume
    echo "Vesta: removed whole-tree /comfyui/output/volume symlink"
  fi

  echo "Vesta: ComfyUI --input-directory /runpod-volume/input"
  echo "Vesta: LoadImage stills     /runpod-volume/input/<file>"
  echo "Vesta: LoadImage last frames /runpod-volume/input/last_frames/<file>"
  echo "Vesta: LoadVideo renders    /runpod-volume/input/vesta_renders/<file>"
  echo "Vesta: SaveVideo output     /runpod-volume/output/vesta -> /comfyui/output/vesta"
fi

# Official worker-comfyui handler base64-encodes history files. Wrap it so
# Vesta production MP4s stay on the volume instead of returning 10–20 s / 4K
# payloads through MCP.
if [ -f /opt/vesta/vesta_handler.py ] && [ -f /handler.py ]; then
  if [ ! -f /handler.orig.py ]; then
    cp /handler.py /handler.orig.py
  fi
  cp /opt/vesta/vesta_handler.py /handler.py
  echo "Vesta: installed volume-persistence handler wrapper"
fi

download_model() {
  local subdir="$1"
  local filename="$2"
  local url="$3"
  local dir="${MODEL_ROOT}/${subdir}"
  local path="${dir}/${filename}"

  if [ -s "${path}" ]; then
    echo "Vesta: model already present: ${path}"
    return 0
  fi

  echo "Vesta: downloading ${filename} to ${dir}"
  aria2c \
    --continue=true \
    --max-connection-per-server=16 \
    --split=16 \
    --min-split-size=1M \
    --file-allocation=none \
    --auto-file-renaming=false \
    --allow-overwrite=true \
    --console-log-level=warn \
    --dir="${dir}" \
    --out="${filename}" \
    "${url}"
}

if [ "${VESTA_DOWNLOAD_MODELS:-1}" = "1" ]; then
  download_model diffusion_models minimax_h3_fl2va_pruned_int8_convrot.safetensors \
    https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors

  download_model text_encoders qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors \
    https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors

  download_model vae minimax_h3_video_vae_fp16.safetensors \
    https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors

  download_model vae minimax_h3_audio_vae_fp32.safetensors \
    https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors
fi

# SeedVR2 4K weights are large (~3.46 GB + VAE). Do not download unless an
# operator explicitly opts in. Place them on the network volume:
#   /runpod-volume/models/diffusion_models/seedvr2_3b_int8_convrot.safetensors
#   /runpod-volume/models/vae/seedvr2_ema_vae_fp16.safetensors
if [ "${VESTA_DOWNLOAD_SEEDVR2:-0}" = "1" ]; then
  download_model diffusion_models seedvr2_3b_int8_convrot.safetensors \
    https://huggingface.co/Comfy-Org/SeedVR2/resolve/main/diffusion_models/seedvr2_3b_int8_convrot.safetensors
  download_model vae seedvr2_ema_vae_fp16.safetensors \
    https://huggingface.co/Comfy-Org/SeedVR2/resolve/main/vae/seedvr2_ema_vae_fp16.safetensors
fi

# Hand control back to the official RunPod worker entrypoint.
exec /start.sh
