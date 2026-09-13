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

# Fast/resumable downloads for the first model bootstrap.
RUN apt-get update \
    && apt-get install -y --no-install-recommends aria2 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p \
    /comfyui/models/diffusion_models \
    /comfyui/models/text_encoders \
    /comfyui/models/vae \
    /opt/vesta

# Extend the official worker's network-volume model discovery to H3 folders.
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
COPY workflows /opt/vesta/workflows
COPY vesta_start.sh /opt/vesta/vesta_start.sh
RUN chmod +x /opt/vesta/vesta_start.sh

ENV VESTA_WORKFLOW_DIR=/opt/vesta/workflows
ENV VESTA_DOWNLOAD_MODELS=1

# Keep the image small: H3 weights are downloaded once to /runpod-volume/models
# when a network volume is attached, then reused across worker restarts.
CMD ["/opt/vesta/vesta_start.sh"]
