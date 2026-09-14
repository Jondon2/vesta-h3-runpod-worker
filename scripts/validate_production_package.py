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
            prefix = str(inputs.get("filename_prefix", ""))
            if prefix.startswith("vesta/"):
                err(
                    f"{rel}: SaveVideo filename_prefix must not start with vesta/ "
                    f"once output root is /runpod-volume/output/vesta (got {prefix!r})"
                )
            elif not prefix.startswith("video/"):
                err(f"{rel}: SaveVideo filename_prefix must start with video/ (got {prefix!r})")
        if cls == "SaveImage":
            prefix = str(inputs.get("filename_prefix", ""))
            if prefix.startswith("vesta/"):
                err(
                    f"{rel}: SaveImage filename_prefix must not start with vesta/ "
                    f"once output root is /runpod-volume/output/vesta (got {prefix!r})"
                )
            elif not prefix.startswith("validation/"):
                err(
                    f"{rel}: SaveImage filename_prefix must start with validation/ (got {prefix!r})"
                )
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
    for key in ("version", "fps", "defaults", "geometry_lock_prompt", "input_image", "output_video", "resolution_catalog", "presets"):
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
            if isinstance(f, str) and f.startswith("vesta/"):
                err(f"{rel}: {preset['id']} output path still uses vesta/ prefix: {f}")
            if isinstance(f, str) and f.endswith(".mp4") and not f.startswith("video/"):
                err(f"{rel}: {preset['id']} MP4 must be under video/: {f}")
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
    out = data.get("output_video") or {}
    if out.get("volume_root") != "/runpod-volume/output/vesta":
        err(f"{rel}: output_video.volume_root must be /runpod-volume/output/vesta")
    if out.get("comfy_saveimage_prefix") != "validation/{name}":
        err(f"{rel}: output_video.comfy_saveimage_prefix mismatch")
    if out.get("comfy_savevideo_prefix") != "video/{name}":
        err(f"{rel}: output_video.comfy_savevideo_prefix mismatch")
    if not out.get("forbid_mcp_base64"):
        err(f"{rel}: output_video.forbid_mcp_base64 must be true")
    if not out.get("forbid_output_symlink"):
        err(f"{rel}: output_video.forbid_output_symlink must be true")


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
    if "ln -sfn /runpod-volume/output /comfyui/output/volume" in text:
        err(f"{rel}: must not symlink the entire Comfy output directory")
    if "ln -sfn /runpod-volume/output/vesta /comfyui/output/vesta" in text:
        err(f"{rel}: must not create output symlink (use --output-directory)")
    if "ln -sfn /comfyui/output/vesta" in text or "ln -sfn /comfyui/output/" in text:
        err(f"{rel}: must not create any /comfyui/output symlink")
    forbidden_links = (
        "ln -sfn /runpod-volume/input /comfyui/input/volume",
        "ln -sfn /runpod-volume/last_frames /comfyui/input/last_frames",
        "ln -sfn /runpod-volume/output/vesta /comfyui/input/vesta_renders",
        "ln -sfn /runpod-volume/input /comfyui/input",
        "ln -sfn /runpod-volume/output/vesta /comfyui/output/vesta",
        "ln -sfn /runpod-volume/output /comfyui/output",
    )
    for needle in forbidden_links:
        if needle in text:
            err(f"{rel}: must not create escaping symlink {needle!r}")
    for line in text.splitlines():
        cmd = line.split("#", 1)[0].strip()
        if cmd.startswith("ln -s") or " ln -s" in f" {cmd}":
            err(f"{rel}: production start must not create any symlink ({cmd})")
    if "--input-directory /runpod-volume/input" not in text:
        err(f"{rel}: must inject ComfyUI --input-directory /runpod-volume/input")
    if "--output-directory /runpod-volume/output/vesta" not in text:
        err(f"{rel}: must inject ComfyUI --output-directory /runpod-volume/output/vesta")
    if (
        "python -u /comfyui/main.py --input-directory /runpod-volume/input "
        "--output-directory /runpod-volume/output/vesta"
    ) not in text:
        err(f"{rel}: must patch every worker-comfyui /start.sh launch line with both directory flags")
    for leftover in (
        "/comfyui/output/vesta",
        "/comfyui/output/volume",
        "/comfyui/input/volume",
        "/comfyui/input/last_frames",
        "/comfyui/input/vesta_renders",
    ):
        if leftover not in text:
            err(f"{rel}: must remove leftover mapping {leftover}")
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
    for script in ("scripts/concat_campaign.sh", "scripts/stage_continuation.sh"):
        proc = subprocess.run(["bash", "-n", str(ROOT / script)], capture_output=True, text=True)
        if proc.returncode != 0:
            err(f"{script}: bash -n failed: {proc.stderr.strip()}")


def _comfy_join(root: str, name: str) -> str:
    """Match ComfyUI folder_paths.get_annotated_filepath / get_save_image_path join."""
    return os.path.abspath(os.path.join(root, name))


def _contained(root: str, path: str) -> bool:
    try:
        return os.path.commonpath((os.path.abspath(root), os.path.abspath(path))) == os.path.abspath(
            root
        )
    except ValueError:
        return False


def validate_comfy_roots() -> None:
    """ComfyUI v0.30.1 realpath jail: input and output roots must contain resolved files."""
    input_root = "/runpod-volume/input"
    output_root = "/runpod-volume/output/vesta"

    name = "vesta_fullres_test.jpg"
    filepath = _comfy_join(input_root, name)
    expected = "/runpod-volume/input/vesta_fullres_test.jpg"
    if filepath != expected:
        err(f"static input resolve: {name!r} -> {filepath!r}, expected {expected!r}")
    elif not _contained(input_root, filepath):
        err(f"static input resolve: {expected} escapes {input_root}")

    old = _comfy_join("/comfyui/input", "volume/vesta_fullres_test.jpg")
    if old == expected:
        err("static input resolve: volume/ prefix must not be the production still path")
    if _contained("/comfyui/input", "/runpod-volume/input/vesta_fullres_test.jpg"):
        err("static input resolve: unexpected containment of volume path under /comfyui/input")

    save_image_prefix = "validation/fullres_input_check"
    save_image_dir = _comfy_join(output_root, os.path.dirname(os.path.normpath(save_image_prefix)))
    expected_save_image_dir = "/runpod-volume/output/vesta/validation"
    if save_image_dir != expected_save_image_dir:
        err(
            f"static SaveImage resolve: {save_image_prefix!r} -> {save_image_dir!r}, "
            f"expected {expected_save_image_dir!r}"
        )
    elif not _contained(output_root, save_image_dir):
        err(f"static SaveImage resolve: {save_image_dir} escapes {output_root}")

    save_video_prefix = "video/Vesta_H3_production"
    save_video_dir = _comfy_join(output_root, os.path.dirname(os.path.normpath(save_video_prefix)))
    expected_save_video_dir = "/runpod-volume/output/vesta/video"
    if save_video_dir != expected_save_video_dir:
        err(
            f"static SaveVideo resolve: {save_video_prefix!r} -> {save_video_dir!r}, "
            f"expected {expected_save_video_dir!r}"
        )
    elif not _contained(output_root, save_video_dir):
        err(f"static SaveVideo resolve: {save_video_dir} escapes {output_root}")

    nested_vesta = _comfy_join(
        output_root, os.path.dirname(os.path.normpath("vesta/fullres_input_check"))
    )
    if nested_vesta == expected_save_image_dir:
        err("static output resolve: leading vesta/ must not be the validation SaveImage path")
    old_symlink_save = _comfy_join("/comfyui/output", "vesta/fullres_input_check")
    if _contained("/comfyui/output", "/runpod-volume/output/vesta/validation"):
        err("static output resolve: unexpected containment of volume output under /comfyui/output")
    if old_symlink_save == expected_save_image_dir:
        err("static output resolve: /comfyui/output/vesta/... must not be the production SaveImage path")


def validate_handler() -> None:
    rel = "vesta_handler.py"
    text = (ROOT / rel).read_text()
    if 'sub == "vesta"' in text or "startswith(\"vesta/\")" in text or "startswith('vesta/')" in text:
        err(f"{rel}: must not key persistence off a vesta/ subfolder name")
    if "os.symlink" in text or "os.symlink" in (ROOT / "scripts/stage_continuation.sh").read_text():
        err("continuation staging must not call os.symlink")
    if "shutil.copy2" not in text:
        err(f"{rel}: continuation staging must copy with shutil.copy2")
    if '"type": "volume"' not in text:
        err(f"{rel}: persistent outputs must be returned as type volume")
    if "skip /view+base64" not in text:
        err(f"{rel}: must skip /view+base64 for persistent outputs")
    if 'kind == "output"' not in text and 'image_type == "output"' not in text:
        err(f"{rel}: must detect Comfy output files via image_type")
    if "/runpod-volume/output/vesta" not in text:
        err(f"{rel}: missing output root /runpod-volume/output/vesta")
    if "/runpod-volume/input" not in text:
        err(f"{rel}: missing input root /runpod-volume/input")
    if "last_frames/" not in text or "vesta_renders/" not in text:
        err(f"{rel}: stage dest must be last_frames/ or vesta_renders/")


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
    if "stage_continuation.sh" not in text:
        err("Dockerfile must COPY stage_continuation.sh")


def validate_github_workflow() -> None:
    text = (ROOT / ".github/workflows/build.yml").read_text()
    if "runtime-v6" not in text:
        err("build.yml must publish runtime-v6")
    if "vesta-h3-runpod-worker:runtime-v5" in text:
        err("build.yml must not retag runtime-v5 (leave it as rollback)")
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
    validate_comfy_roots()
    validate_handler()
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
