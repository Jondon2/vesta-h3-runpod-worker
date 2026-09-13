#!/usr/bin/env python3
"""Wrap worker-comfyui so Vesta production videos persist on the volume.

The official handler (5.8.6) fetches Comfy /view files and base64-encodes them
into the job result. That is fine for a 1 MB 5 s probe. It is not acceptable
for 10–20 s or 4K MP4s through MCP.

SaveVideo prefixes of ``vesta/...`` write under /comfyui/output/vesta, which
vesta_start.sh maps to /runpod-volume/output/vesta. Those files are skipped
for byte fetch; the job result carries a volume path instead.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys

import runpod

ORIG_PATH = os.environ.get("VESTA_ORIG_HANDLER", "/handler.orig.py")
VOLUME_OUTPUT = "/runpod-volume/output/vesta"
SENTINEL = b"VESTA_VOLUME_V1\n"


def _load_orig():
    spec = importlib.util.spec_from_file_location("worker_comfyui_handler", ORIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load original handler from {ORIG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orig = _load_orig()
_orig_get_image_data = orig.get_image_data


def _is_vesta_subfolder(subfolder: str) -> bool:
    sub = (subfolder or "").replace("\\", "/").strip("/")
    return sub == "vesta" or sub.startswith("vesta/")


def get_image_data(filename, subfolder, image_type):
    if not _is_vesta_subfolder(subfolder):
        return _orig_get_image_data(filename, subfolder, image_type)

    sub = (subfolder or "").replace("\\", "/").strip("/")
    rel = f"{sub}/{filename}" if sub else filename
    candidates = [
        os.path.join("/runpod-volume/output", rel),
        os.path.join("/comfyui/output", rel),
        os.path.join(VOLUME_OUTPUT, os.path.basename(filename)),
    ]
    volume_path = candidates[0]
    size = None
    for path in candidates:
        if os.path.isfile(path):
            volume_path = os.path.realpath(path)
            size = os.path.getsize(path)
            break

    payload = {
        "filename": filename,
        "subfolder": sub,
        "path": volume_path,
        "size_bytes": size,
    }
    print(
        f"vesta-handler - skip /view+base64 for {rel}; persist {volume_path} size={size}"
    )
    return SENTINEL + json.dumps(payload).encode("utf-8")


orig.get_image_data = get_image_data


def _rewrite_result(result):
    if not isinstance(result, dict):
        return result
    images = result.get("images")
    if not images:
        result.setdefault(
            "vesta_persistence",
            {
                "input": "/runpod-volume/input",
                "output": VOLUME_OUTPUT,
            },
        )
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
                "subfolder": meta.get("subfolder", "vesta"),
            }
        )
    result["images"] = rewritten
    result["vesta_persistence"] = {
        "input": "/runpod-volume/input",
        "output": VOLUME_OUTPUT,
    }
    return result


def handler(job):
    return _rewrite_result(orig.handler(job))


if __name__ == "__main__":
    print("vesta-handler - starting (volume persistence wrapper over worker-comfyui)")
    if not os.path.isfile(ORIG_PATH):
        print(f"vesta-handler - missing {ORIG_PATH}", file=sys.stderr)
        sys.exit(1)
    runpod.serverless.start({"handler": handler})
