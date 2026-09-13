FROM runpod/worker-comfyui:5.8.6-base

# MiniMax H3 native nodes require a recent ComfyUI release.
RUN cd /comfyui \
    && git fetch --depth 1 origin refs/tags/v0.30.1 \
    && git checkout FETCH_HEAD \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir --force-reinstall \
       torch==2.12.0 torchvision torchaudio \
       --index-url https://download.pytorch.org/whl/cu126

RUN mkdir -p \
    /comfyui/models/diffusion_models \
    /comfyui/models/text_encoders \
    /comfyui/models/vae

COPY workflows /opt/vesta/workflows

ENV VESTA_WORKFLOW_DIR=/opt/vesta/workflows
