#!/usr/bin/env python3
"""Wrap worker-comfyui so Vesta production files persist on the volume.

The official handler (5.8.6) fetches Comfy /view files and base64-encodes them
into the job result. That is fine for a 1 MB 5 s probe. It is not acceptable
for 10–20 s or 4K MP4s through MCP.

runtime-v6 makes /runpod-volume/output/vesta ComfyUI's real --output-directory.
History entries with image_type=output therefore already live on the volume.
Those files are skipped for byte fetch; the job result carries a volume path.

Temp/input files still go through the official /view + base64 path.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import shutil
import sys

import runpod

ORIG_PATH = os.environ.get("VESTA_ORIG_HANDLER", "/handler.orig.py")
INPUT_ROOT = os.environ.get("VESTA_INPUT_ROOT", "/runpod-volume/input")
VOLUME_OUTPUT = os.environ.get("VESTA_OUTPUT_ROOT", "/runpod-volume/output/vesta")
SENTINEL = b"VESTA_VOLUME_V1\n"
STAGE_DEST_PREFIXES = ("last_frames/", "vesta_renders/")


def _load_orig():
    spec = importlib.util.spec_from_file_location("worker_comfyui_handler", ORIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load original handler from {ORIG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orig = _load_orig()
_orig_get_image_data = orig.get_image_data


def _is_within(root: str, path: str) -> bool:
    try:
        root_r = os.path.realpath(root)
        path_r = os.path.realpath(path)
        return os.path.commonpath((root_r, path_r)) == root_r
    except ValueError:
        return False


def _volume_output_available() -> bool:
    return os.path.isdir(VOLUME_OUTPUT)


def _resolve_output_path(filename: str, subfolder: str) -> str:
    sub = (subfolder or "").replace("\\", "/").strip("/")
    rel = f"{sub}/{filename}" if sub else filename
    return os.path.join(VOLUME_OUTPUT, rel)


def _is_persistent_output(filename, subfolder, image_type) -> bool:
    """Skip /view+base64 for production output files on the volume.

    Prefer image_type == 'output' once --output-directory is the volume.
    Also treat a resolved path inside VOLUME_OUTPUT as persistent. Never skip
    temp/input files; those stay on the official handler path.
    """
    kind = (image_type or "").strip().lower()
    if kind in ("temp", "input"):
        return False
    if not _volume_output_available():
        return False
    if kind == "output":
        return True
    resolved = _resolve_output_path(filename, subfolder)
    return _is_within(VOLUME_OUTPUT, resolved)


def get_image_data(filename, subfolder, image_type):
    if not _is_persistent_output(filename, subfolder, image_type):
        return _orig_get_image_data(filename, subfolder, image_type)

    volume_path = _resolve_output_path(filename, subfolder)
    size = None
    if os.path.isfile(volume_path):
        volume_path = os.path.realpath(volume_path)
        size = os.path.getsize(volume_path)
        if not _is_within(VOLUME_OUTPUT, volume_path):
            return _orig_get_image_data(filename, subfolder, image_type)

    sub = (subfolder or "").replace("\\", "/").strip("/")
    payload = {
        "filename": filename,
        "subfolder": sub,
        "path": volume_path,
        "size_bytes": size,
        "image_type": image_type,
    }
    print(
        f"vesta-handler - skip /view+base64 for output {sub}/{filename}; "
        f"persist {volume_path} size={size}"
    )
    return SENTINEL + json.dumps(payload).encode("utf-8")


orig.get_image_data = get_image_data


def _persistence_meta():
    return {
        "input": INPUT_ROOT,
        "output": VOLUME_OUTPUT,
    }


def _rewrite_result(result):
    if not isinstance(result, dict):
        return result
    images = result.get("images")
    if not images:
        result.setdefault("vesta_persistence", _persistence_meta())
        return result

    rewritten = []
    for img in images:
        if not isinstance(img, dict) or img.get("type") != "base64":
            rewritten.append(img)
            continue
        data = img.get("data")
        if not isinstance(data, str):
            rewritten.append(img)
            continue
        try:
            raw = base64.b64decode(data)
        except Exception:
            rewritten.append(img)
            continue
        if not raw.startswith(SENTINEL):
            rewritten.append(img)
            continue
        meta = json.loads(raw[len(SENTINEL) :].decode("utf-8"))
        rewritten.append(
            {
                "filename": meta.get("filename") or img.get("filename"),
                "type": "volume",
                "path": meta.get("path"),
                "size_bytes": meta.get("size_bytes"),
                "subfolder": meta.get("subfolder", ""),
            }
        )
    result["images"] = rewritten
    result["vesta_persistence"] = _persistence_meta()
    return result


def _stage_one(src_rel: str, dest_rel: str) -> dict:
    """Copy a volume output into input/last_frames or input/vesta_renders.

    Never creates a symlink. Dest must stay inside those two input subdirs.
    """
    src_rel = (src_rel or "").replace("\\", "/").lstrip("/")
    dest_rel = (dest_rel or "").replace("\\", "/").lstrip("/")
    if not dest_rel.startswith(STAGE_DEST_PREFIXES):
        raise ValueError(
            f"stage dest must start with last_frames/ or vesta_renders/ (got {dest_rel!r})"
        )
    src = os.path.join(VOLUME_OUTPUT, src_rel)
    dest = os.path.join(INPUT_ROOT, dest_rel)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"stage src missing: {src}")
    if not _is_within(VOLUME_OUTPUT, src):
        raise ValueError(f"stage src escapes output root: {src}")
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)
    if not _is_within(INPUT_ROOT, dest):
        raise ValueError(f"stage dest escapes input root: {dest}")
    if os.path.islink(dest):
        os.unlink(dest)
    shutil.copy2(src, dest)
    if os.path.islink(dest):
        os.unlink(dest)
        raise RuntimeError(f"refusing symlink dest {dest}")
    return {
        "src": os.path.realpath(src),
        "dest": os.path.realpath(dest),
        "size_bytes": os.path.getsize(dest),
        "method": "copy",
    }


def _stage_continuations(job_input, result: dict) -> None:
    if not isinstance(job_input, dict):
        return
    items = job_input.get("vesta_stage")
    if not items:
        return
    if not isinstance(items, list):
        items = [items]
    staged = []
    errors = result.setdefault("errors", []) if isinstance(result, dict) else []
    for item in items:
        if not isinstance(item, dict):
            errors.append("vesta_stage item must be an object with src and dest")
            continue
        try:
            staged.append(_stage_one(item.get("src") or "", item.get("dest") or ""))
        except Exception as exc:
            errors.append(f"vesta_stage failed: {exc}")
    if staged:
        result["vesta_staged"] = staged
    if errors == []:
        result.pop("errors", None)


def handler(job):
    result = _rewrite_result(orig.handler(job))
    if isinstance(result, dict):
        _stage_continuations(job.get("input") or {}, result)
    return result


if __name__ == "__main__":
    print("vesta-handler - starting (volume persistence wrapper over worker-comfyui)")
    if not os.path.isfile(ORIG_PATH):
        print(f"vesta-handler - missing {ORIG_PATH}", file=sys.stderr)
        sys.exit(1)
    runpod.serverless.start({"handler": handler})
