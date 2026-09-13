FROM runpod/worker-comfyui:5.8.6-base

# MiniMax H3 native nodes require a recent ComfyUI release.
# This image targets RTX PRO 6000 Blackwell (sm_120), so use the CUDA 13.0
# PyTorch wheel. CUDA 12.6 wheels do not carry Blackwell kernels.
RUN cd /comfyui \
    && git fetch --depth 1 origin refs/tags/v0.30.1 \
    && git checkout FETCH_HEAD \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir --force-reinstall \
       torch==2.12.0 torchvision torchaudio \
       --index-url https://download.pytorch.org/whl/cu130

COPY check_arch.py /tmp/check_arch.py
RUN /opt/venv/bin/python /tmp/check_arch.py sm_120 && rm /tmp/check_arch.py

RUN mkdir -p \
    /comfyui/models/diffusion_models \
    /comfyui/models/text_encoders \
    /comfyui/models/vae

COPY workflows /opt/vesta/workflows

ENV VESTA_WORKFLOW_DIR=/opt/vesta/workflows
