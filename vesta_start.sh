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

# Full-resolution listing stills and production renders live on the network
# volume so job payloads stay small (workflow JSON only). Do not send original
# JPEGs or production MP4s as MCP/base64.
#
# ComfyUI v0.30.1 LoadImage/LoadVideo/SaveImage/SaveVideo call
# exists_annotated_filepath / get_save_image_path, which reject any path whose
# realpath escapes the configured root (symlink jail). Do NOT ln -s volume dirs
# into /comfyui/input or /comfyui/output. Make the volume the real roots:
#   --input-directory  /runpod-volume/input
#   --output-directory /runpod-volume/output/vesta
#
# worker-comfyui 5.8.6 /start.sh hardcodes:
#   python -u /comfyui/main.py --disable-auto-launch --disable-metadata ...
# It does not forward extra argv or an env var. Inject both directory flags
# into every /comfyui/main.py launch line before exec /start.sh.
#
# Continuation stills/MP4s are copied into last_frames/ or vesta_renders/.
# Never symlink generated output back into the input root.
INPUT_ROOT="/runpod-volume/input"
OUTPUT_ROOT="/runpod-volume/output/vesta"
if [ -d /runpod-volume ] && [ -w /runpod-volume ]; then
  mkdir -p \
    /runpod-volume/input \
    /runpod-volume/input/last_frames \
    /runpod-volume/input/vesta_renders \
    /runpod-volume/output/vesta
  mkdir -p /comfyui/input /comfyui/output

  # runtime-v4/v5 leftover aliases. Never leave these for Load*/Save*.
  for leftover in \
    /comfyui/input/volume \
    /comfyui/input/last_frames \
    /comfyui/input/vesta_renders \
    /comfyui/output/vesta \
    /comfyui/output/volume
  do
    if [ -L "${leftover}" ]; then
      rm -f "${leftover}"
      echo "Vesta: removed leftover symlink ${leftover}"
    elif [ -e "${leftover}" ]; then
      mv "${leftover}" "${leftover}.ephemeral.$$"
      echo "Vesta: moved leftover ${leftover} aside (not a symlink)"
    fi
  done

  if [ ! -f /start.sh ]; then
    echo "Vesta: FATAL: /start.sh missing; cannot inject ComfyUI directory flags" >&2
    exit 1
  fi
  if ! grep -q 'python -u /comfyui/main.py' /start.sh; then
    echo "Vesta: FATAL: /start.sh does not launch python -u /comfyui/main.py" >&2
    exit 1
  fi

  LAUNCH_PREFIX='python -u /comfyui/main.py --input-directory /runpod-volume/input --output-directory /runpod-volume/output/vesta'
  if ! grep -q -- '--input-directory /runpod-volume/input' /start.sh || \
     ! grep -q -- '--output-directory /runpod-volume/output/vesta' /start.sh; then
    # Strip a prior partial injection, then apply both flags to every launch line.
    sed -i 's|python -u /comfyui/main.py --input-directory /runpod-volume/input --output-directory /runpod-volume/output/vesta|python -u /comfyui/main.py|g' /start.sh
    sed -i 's|python -u /comfyui/main.py --input-directory /runpod-volume/input|python -u /comfyui/main.py|g' /start.sh
    sed -i 's|python -u /comfyui/main.py --output-directory /runpod-volume/output/vesta|python -u /comfyui/main.py|g' /start.sh
    sed -i "s|python -u /comfyui/main.py|${LAUNCH_PREFIX}|g" /start.sh
  fi
  if ! grep -q -- '--input-directory /runpod-volume/input' /start.sh; then
    echo "Vesta: FATAL: failed to inject --input-directory into /start.sh" >&2
    exit 1
  fi
  if ! grep -q -- '--output-directory /runpod-volume/output/vesta' /start.sh; then
    echo "Vesta: FATAL: failed to inject --output-directory into /start.sh" >&2
    exit 1
  fi

  export VESTA_INPUT_ROOT="${INPUT_ROOT}"
  export VESTA_OUTPUT_ROOT="${OUTPUT_ROOT}"

  echo "Vesta: ComfyUI --input-directory ${INPUT_ROOT}"
  echo "Vesta: ComfyUI --output-directory ${OUTPUT_ROOT}"
  echo "Vesta: injected launch: ${LAUNCH_PREFIX} --disable-auto-launch --disable-metadata ..."
  echo "Vesta: LoadImage stills      ${INPUT_ROOT}/<file>"
  echo "Vesta: LoadImage last frames ${INPUT_ROOT}/last_frames/<file>"
  echo "Vesta: LoadVideo renders     ${INPUT_ROOT}/vesta_renders/<file>"
  echo "Vesta: SaveImage/SaveVideo   ${OUTPUT_ROOT}/<prefix>/... (no symlink)"
fi

# Official worker-comfyui handler base64-encodes history files. Wrap it so
# Vesta production files stay on the volume instead of returning 10–20 s / 4K
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
