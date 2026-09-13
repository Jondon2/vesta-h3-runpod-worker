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
  "${MODEL_ROOT}/vae"

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

# Hand control back to the official RunPod worker entrypoint.
exec /start.sh
