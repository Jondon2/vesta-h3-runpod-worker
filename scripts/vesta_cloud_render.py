#!/usr/bin/env python3
"""Render one non-destructive POST_005 V4 pair on a short-lived RunPod pod.

The persistent volume is prepared once by the asset-seeding procedure.  This
worker deliberately never modifies a historical V4 folder: every invocation
requires a fresh relative revision path and destroys its GPU pod in ``finally``.
Only compact stills are copied to a GitHub Release so Astra can QC them later
without keeping a GPU online.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_TAG = "vesta-production-artifacts"
POD_IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
REMOTE_ROOT = "/workspace/vesta-v12"


def run(command: list[str], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(f"{command[0]}: {detail}")
    return result


def json_output(result: subprocess.CompletedProcess[str]) -> dict:
    """Extract the final JSON document without relying on cosmetic CLI logs."""
    output = result.stdout.strip()
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        start = output.find("{")
    if start < 0:
        raise RuntimeError("RunPod did not return pod JSON")
    return json.loads(output[start:])


def require_relative_revision(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not re.fullmatch(r"stills_[a-z0-9_]+", value):
        raise ValueError("revision must be a new, relative stills_<pair>_<revision> directory")
    return value


def ssh_args(key_path: Path, host: str, port: int, known_hosts: Path) -> list[str]:
    return [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={known_hosts}",
        "-i", str(key_path), "-p", str(port), f"root@{host}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=["LANTERN", "WOOL", "OAK"], required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--volume-id", required=True)
    parser.add_argument("--data-center", default="US-IL-1")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    revision = require_relative_revision(args.revision)
    if not os.environ.get("RUNPOD_API_KEY", "").strip():
        raise SystemExit("MISSING_GITHUB_SECRET: RUNPOD_API_KEY")

    mode = args.pair.lower()
    pod_id: str | None = None
    key_name = f"vesta-controller-{uuid.uuid4().hex[:12]}"
    result: dict[str, object] = {"pair": args.pair, "revision": revision, "pod_deleted": False}
    with tempfile.TemporaryDirectory(prefix="vesta-render-") as temporary:
        temp = Path(temporary)
        key_path = temp / "id_ed25519"
        known_hosts = temp / "known_hosts"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", key_name, "-f", str(key_path)])
        try:
            run(["runpodctl", "ssh", "add-key", "--key-file", str(key_path) + ".pub"])
            created = run([
                "runpodctl", "pod", "create", "--name", f"vesta-post005-{mode}-{uuid.uuid4().hex[:8]}",
                "--image", POD_IMAGE, "--gpu-id", "NVIDIA GeForce RTX 4090", "--gpu-count", "1",
                "--data-center-ids", args.data_center, "--network-volume-id", args.volume_id,
                "--volume-mount-path", "/workspace", "--ports", "22/tcp", "--wait", "--wait-timeout", "10m",
            ])
            pod = json_output(created)
            pod_id = str(pod["id"])
            result["pod_id"] = pod_id
            info = json_output(run(["runpodctl", "ssh", "info", pod_id]))
            host, port = str(info["ip"]), int(info["port"])
            remote = (
                "set -eu; "
                f"base={REMOTE_ROOT}; "
                'test -d "$base/external/vesta-assets/blender/assets"; '
                'test -x "$base/runtime/blender-5.2.2-linux-x64/blender"; '
                'test -f "$base/production/12post_20260930/delivery/POST_005/v4/build_scene.py"; '
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; "
                'VESTA_ASSETS="$base/external/vesta-assets/blender/assets" '
                'VESTA_V4_ROOT="$base/production/12post_20260930/delivery/POST_005/v4" '
                'VESTA_CYCLES_BACKENDS=OPTIX,CUDA '
                '"$base/runtime/blender-5.2.2-linux-x64/blender" --background --python '
                '"$base/production/12post_20260930/delivery/POST_005/v4/build_scene.py" '
                f"-- {mode} {revision}; "
                f'source="$base/production/12post_20260930/delivery/POST_005/v4/{revision}"; '
                f'artifact="$base/artifacts/POST_005/{args.pair}/{revision}"; '
                'mkdir -p "$artifact"; '
                f'cp "$source/{args.pair}_BEFORE.png" "$source/{args.pair}_AFTER.png" "$artifact/"; '
                f'test -s "$artifact/{args.pair}_BEFORE.png"; '
                f'test -s "$artifact/{args.pair}_AFTER.png"'
            )
            rendered = run(ssh_args(key_path, host, port, known_hosts) + [remote])
            if "CYCLES_GPU PASS" not in rendered.stdout:
                raise RuntimeError("CYCLES_GPU verification did not pass")
            result["cycles_gpu"] = "PASS"
            stage = temp / "artifacts"
            stage.mkdir()
            remote_prefix = f"root@{host}:{REMOTE_ROOT}/artifacts/POST_005/{args.pair}/{revision}"
            for side in ("BEFORE", "AFTER"):
                target = stage / f"POST_005_{args.pair}_{revision.upper()}_{side}.png"
                run([
                    "scp", "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={known_hosts}",
                    "-i", str(key_path), "-P", str(port), f"{remote_prefix}/{args.pair}_{side}.png", str(target),
                ])
            run(["gh", "release", "upload", RELEASE_TAG, "--repo", args.repo, *(str(path) for path in stage.iterdir())])
            result.update({
                "artifact_location": {
                    "provider": "github_release", "release_tag": RELEASE_TAG,
                    "before_asset": f"POST_005_{args.pair}_{revision.upper()}_BEFORE.png",
                    "after_asset": f"POST_005_{args.pair}_{revision.upper()}_AFTER.png",
                    "volume_path": f"artifacts/POST_005/{args.pair}/{revision}",
                },
                "remote_output": f"{REMOTE_ROOT}/production/12post_20260930/delivery/POST_005/v4/{revision}",
            })
        finally:
            if pod_id:
                deleted = run(["runpodctl", "pod", "delete", pod_id], check=False)
                result["pod_deleted"] = deleted.returncode == 0
            run(["runpodctl", "ssh", "remove-key", "--name", key_name], check=False)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
