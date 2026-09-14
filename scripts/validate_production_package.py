#!/usr/bin/env python3
"""Static checks for the Vesta production package. No GPU, no downloads."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMFY_V030_CLASSES = {
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "LoadImage",
    "LoadVideo",
    "GetVideoComponents",
    "MiniMaxH3ImageToVideo",
    "RandomNoise",
    "BasicGuider",
    "KSamplerSelect",
    "BasicScheduler",
    "SamplerCustomAdvanced",
    "KSampler",
    "VAEDecode",
    "VAEDecodeAudio",
    "VAEEncodeTiled",
    "VAEDecodeTiled",
    "CreateVideo",
    "SaveVideo",
    "SaveImage",
    "ImageScale",
    "SeedVR2Preprocess",
    "SeedVR2PostProcessing",
    "SeedVR2Conditioning",
    "SeedVR2TemporalChunk",
    "SeedVR2TemporalMerge",
}

FORBIDDEN_SEEDVR2_CLASSES = {
    "SeedVR2LoadModel",
    "SeedVR2VideoUpscale",
}

PRESET_REQUIRED = {
    "id",
    "name",
    "camera_prompt",
    "geometry_lock_prompt",
    "ending_instructions",
    "duration_seconds",
    "frame_count",
    "fps",
    "recommended_steps",
    "sampler",
    "scheduler",
    "resolution_rules",
    "intended_use_case",
    "expected_output_structure",
}

QC_REQUIRED = {"id", "name", "checks"}

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        err(f"JSON syntax {path.relative_to(ROOT)}: {e}")
        return None


def validate_workflow(path: Path, data: dict) -> None:
    rel = str(path.relative_to(ROOT))
    if not isinstance(data, dict) or not data:
        err(f"{rel}: empty or not an object")
        return
    for node_id, node in data.items():
        if not isinstance(node, dict):
            err(f"{rel}: node {node_id!r} is not an object")
            continue
        cls = node.get("class_type")
        if not cls:
            err(f"{rel}: node {node_id!r} missing class_type")
            continue
        if cls in FORBIDDEN_SEEDVR2_CLASSES:
            err(f"{rel}: {node_id} uses retired class {cls} (use native ComfyUI v0.30.1 SeedVR2 nodes)")
        if cls not in COMFY_V030_CLASSES:
            err(f"{rel}: unknown class_type {cls} on node {node_id}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            err(f"{rel}: node {node_id} missing inputs object")
            continue
        for key, value in inputs.items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                if value[0] not in data:
                    err(f"{rel}: {node_id}.{key} references missing node {value[0]!r}")
        if cls == "SaveVideo":
            prefix = inputs.get("filename_prefix", "")
            if not str(prefix).startswith("vesta/"):
                err(f"{rel}: SaveVideo filename_prefix must start with vesta/ (got {prefix!r})")
        if cls == "LoadImage":
            image = str(inputs.get("image", ""))
            if image.startswith("volume/"):
                err(
                    f"{rel}: LoadImage must not use volume/ (ComfyUI realpath jail); "
                    f"use a path relative to /runpod-volume/input (got {image!r})"
                )
            elif image and "/" in image and not image.startswith("last_frames/"):
                err(f"{rel}: LoadImage subdir must be last_frames/ (got {image!r})")
        if cls == "LoadVideo":
            file = str(inputs.get("file", ""))
            if file and not file.startswith("vesta_renders/"):
                err(f"{rel}: LoadVideo should read vesta_renders/ (got {file!r})")


def validate_presets(data: dict) -> None:
    rel = "config/vesta_shot_presets.json"
    for key in ("version", "fps", "defaults", "geometry_lock_prompt", "input_image", "resolution_catalog", "presets"):
        if key not in data:
            err(f"{rel}: missing {key}")
    presets = data.get("presets") or []
    if len(presets) != 9:
        err(f"{rel}: expected 9 presets, got {len(presets)}")
    ids = []
    for i, preset in enumerate(presets):
        missing = PRESET_REQUIRED - set(preset)
        if missing:
            err(f"{rel}: preset[{i}] missing {sorted(missing)}")
            continue
        ids.append(preset["id"])
        rules = preset["resolution_rules"]
        if not rules.get("forbid_native_4k"):
            err(f"{rel}: {preset['id']} must forbid native 4K")
        files = preset.get("expected_output_structure", {}).get("files") or []
        for f in files:
            if isinstance(f, str) and f.startswith("video/"):
                err(f"{rel}: {preset['id']} output path still uses video/ prefix: {f}")
        wf = preset.get("expected_output_structure", {}).get("workflow")
        if wf:
            if not (ROOT / wf).is_file():
                err(f"{rel}: {preset['id']} workflow {wf} does not exist")
    if len(ids) != len(set(ids)):
        err(f"{rel}: duplicate preset ids")
    inp = data.get("input_image") or {}
    if inp.get("comfy_loadimage_name") != "{listing_id}{ext}":
        err(f"{rel}: input_image.comfy_loadimage_name mismatch")
    if not inp.get("forbid_mcp_base64"):
        err(f"{rel}: input_image.forbid_mcp_base64 must be true")


def validate_qc(data: dict) -> None:
    rel = "config/astra_qc_categories.json"
    if data.get("fail_closed") != ["morphing", "object_count", "geometry_drift", "ending_composition"]:
        err(f"{rel}: fail_closed list mismatch")
    cats = data.get("categories") or []
    if len(cats) < 8:
        err(f"{rel}: expected at least 8 categories")
    for cat in cats:
        missing = QC_REQUIRED - set(cat)
        if missing:
            err(f"{rel}: category {cat.get('id')} missing {sorted(missing)}")
        if not isinstance(cat.get("checks"), list) or not cat["checks"]:
            err(f"{rel}: category {cat.get('id')} has empty checks")


def validate_extra_model_paths(text: str) -> None:
    rel = "extra_model_paths.yaml"
    for needle in (
        "base_path: /runpod-volume",
        "diffusion_models:",
        "text_encoders:",
        "vae:",
        "upscale_models:",
    ):
        if needle not in text:
            err(f"{rel}: missing {needle!r}")
    if "seedvr2_3b_int8_convrot.safetensors" not in text:
        err(f"{rel}: must document SeedVR2 3B INT8 filename")
    if "seedvr2_ema_vae_fp16.safetensors" not in text:
        err(f"{rel}: must document SeedVR2 VAE filename")


def validate_start_script() -> None:
    rel = "vesta_start.sh"
    text = (ROOT / rel).read_text()
    if "/comfyui/output/volume" in text and "ln -sfn /runpod-volume/output /comfyui/output/volume" in text:
        err(f"{rel}: must not symlink the entire Comfy output directory")
    if "ln -sfn /runpod-volume/output/vesta /comfyui/output/vesta" not in text:
        err(f"{rel}: missing Vesta-specific output symlink")
    forbidden_input_links = (
        "ln -sfn /runpod-volume/input /comfyui/input/volume",
        "ln -sfn /runpod-volume/last_frames /comfyui/input/last_frames",
        "ln -sfn /runpod-volume/output/vesta /comfyui/input/vesta_renders",
        "ln -sfn /runpod-volume/input /comfyui/input",
    )
    for needle in forbidden_input_links:
        if needle in text:
            err(f"{rel}: must not create LoadImage/LoadVideo symlink {needle!r}")
    if "--input-directory /runpod-volume/input" not in text:
        err(f"{rel}: must inject ComfyUI --input-directory /runpod-volume/input")
    if "python -u /comfyui/main.py --input-directory /runpod-volume/input" not in text:
        err(f"{rel}: must patch worker-comfyui /start.sh launch line (it does not forward argv)")
    for path in (
        "/runpod-volume/input",
        "/runpod-volume/input/last_frames",
        "/runpod-volume/input/vesta_renders",
        "/runpod-volume/output/vesta",
    ):
        if path not in text:
            err(f"{rel}: missing mkdir path {path}")
    proc = subprocess.run(["bash", "-n", str(ROOT / rel)], capture_output=True, text=True)
    if proc.returncode != 0:
        err(f"{rel}: bash -n failed: {proc.stderr.strip()}")
    concat = ROOT / "scripts/concat_campaign.sh"
    proc = subprocess.run(["bash", "-n", str(concat)], capture_output=True, text=True)
    if proc.returncode != 0:
        err(f"scripts/concat_campaign.sh: bash -n failed: {proc.stderr.strip()}")


def validate_comfy_input_root_resolution() -> None:
    """ComfyUI v0.30.1 folder_paths.get_annotated_filepath / is_within_directory."""
    input_root = "/runpod-volume/input"
    name = "vesta_fullres_test.jpg"
    filepath = os.path.abspath(os.path.join(input_root, name))
    expected = "/runpod-volume/input/vesta_fullres_test.jpg"
    if filepath != expected:
        err(f"static input resolve: {name!r} -> {filepath!r}, expected {expected!r}")
        return
    try:
        contained = os.path.commonpath((os.path.abspath(input_root), filepath)) == os.path.abspath(
            input_root
        )
    except ValueError:
        contained = False
    if not contained:
        err(f"static input resolve: {expected} escapes {input_root}")
    old = os.path.abspath(os.path.join("/comfyui/input", "volume/vesta_fullres_test.jpg"))
    if old == expected:
        err("static input resolve: volume/ prefix must not be the production still path")
    # Directory symlink to the volume still fails the jail even when the file exists.
    if os.path.commonpath(("/comfyui/input", "/runpod-volume/input/vesta_fullres_test.jpg")) == "/comfyui/input":
        err("static input resolve: unexpected containment of volume path under /comfyui/input")


def validate_dockerfile() -> None:
    text = (ROOT / "Dockerfile").read_text()
    if "runtime-v3" in text:
        err("Dockerfile should not pin runtime-v3 as the new image tag")
    if "ffmpeg" not in text:
        err("Dockerfile must install/verify ffmpeg")
    if "vesta_handler.py" not in text:
        err("Dockerfile must COPY vesta_handler.py")
    if "concat_campaign.sh" not in text:
        err("Dockerfile must COPY concat_campaign.sh")


def validate_github_workflow() -> None:
    text = (ROOT / ".github/workflows/build.yml").read_text()
    if "runtime-v5" not in text:
        err("build.yml must publish runtime-v5")
    if "vesta-h3-runpod-worker:runtime-v4" in text:
        err("build.yml must not retag runtime-v4 (leave it as rollback)")
    if "vesta-h3-runpod-worker:runtime-v3" in text:
        err("build.yml must not retag runtime-v3 (leave it as rollback)")


def main() -> int:
    os.chdir(ROOT)
    for path in sorted((ROOT / "workflows").glob("*.json")):
        data = load_json(path)
        if isinstance(data, dict):
            validate_workflow(path, data)
    presets = load_json(ROOT / "config/vesta_shot_presets.json")
    if isinstance(presets, dict):
        validate_presets(presets)
    qc = load_json(ROOT / "config/astra_qc_categories.json")
    if isinstance(qc, dict):
        validate_qc(qc)
    validate_extra_model_paths((ROOT / "extra_model_paths.yaml").read_text())
    validate_start_script()
    validate_comfy_input_root_resolution()
    validate_dockerfile()
    validate_github_workflow()

    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK: production package validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
