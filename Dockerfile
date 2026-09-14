FROM runpod/worker-comfyui:5.8.6-base

# MiniMax H3 native nodes require a recent ComfyUI release.
# RTX PRO 6000 Blackwell is sm_120, so use the CUDA 13.0 PyTorch wheel.
RUN cd /comfyui \
    && git fetch --depth 1 origin refs/tags/v0.30.1 \
    && git checkout FETCH_HEAD \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir --force-reinstall \
       torch==2.12.0 torchvision torchaudio \
       --index-url https://download.pytorch.org/whl/cu130

COPY check_arch.py /tmp/check_arch.py
RUN /opt/venv/bin/python /tmp/check_arch.py sm_120 && rm /tmp/check_arch.py

# aria2: first-boot H3 downloads. ffmpeg/ffprobe: SaveVideo/CreateVideo already
# use PyAV, but campaign two-shot concat and delivery probes need the ffmpeg CLI.
# The 5.8.6-base image already installs ffmpeg; pin it again so a future base
# drop cannot silently remove it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends aria2 ffmpeg \
    && ffmpeg -version \
    && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p \
    /comfyui/models/diffusion_models \
    /comfyui/models/text_encoders \
    /comfyui/models/vae \
    /opt/vesta/scripts \
    /opt/vesta/workflows \
    /opt/vesta/config

# Extend the official worker's network-volume model discovery to H3 + SeedVR2 folders.
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflows /opt/vesta/workflows
COPY config /opt/vesta/config
COPY vesta_start.sh /opt/vesta/vesta_start.sh
COPY vesta_handler.py /opt/vesta/vesta_handler.py
COPY scripts/concat_campaign.sh /opt/vesta/scripts/concat_campaign.sh
COPY scripts/stage_continuation.sh /opt/vesta/scripts/stage_continuation.sh
RUN chmod +x /opt/vesta/vesta_start.sh /opt/vesta/scripts/concat_campaign.sh /opt/vesta/scripts/stage_continuation.sh

ENV VESTA_WORKFLOW_DIR=/opt/vesta/workflows
ENV VESTA_DOWNLOAD_MODELS=1
ENV VESTA_DOWNLOAD_SEEDVR2=0
ENV PATH="/opt/vesta/scripts:${PATH}"

# Keep the image small: H3 weights are downloaded once to /runpod-volume/models
# when a network volume is attached, then reused across worker restarts.
# Do not bake SeedVR2 weights into this layer.
CMD ["/opt/vesta/vesta_start.sh"]
