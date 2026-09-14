#!/usr/bin/env bash
# Copy a production output into the ComfyUI input root for continuation.
# Use this for last frames, FL2VA references, or SeedVR2 LoadVideo sources.
# Never creates a symlink. Does not start a GPU worker.
set -euo pipefail

INPUT_ROOT="${VESTA_INPUT_ROOT:-/runpod-volume/input}"
OUTPUT_ROOT="${VESTA_OUTPUT_ROOT:-/runpod-volume/output/vesta}"

usage() {
  echo "Usage: $0 <src-relative-to-output-root> <dest-under-last_frames-or-vesta_renders>" >&2
  echo "Example: $0 video/Vesta_H3_campaign-a_00001_.mp4 vesta_renders/Vesta_H3_campaign-a_00001_.mp4" >&2
  exit 2
}

[ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && usage
[ "$#" -eq 2 ] || usage

SRC_REL=${1#/}
DEST_REL=${2#/}

case "${DEST_REL}" in
  last_frames/*|vesta_renders/*) ;;
  *)
    echo "dest must start with last_frames/ or vesta_renders/" >&2
    exit 1
    ;;
esac

SRC="${OUTPUT_ROOT}/${SRC_REL}"
DEST="${INPUT_ROOT}/${DEST_REL}"

[ -f "${SRC}" ] || { echo "missing source: ${SRC}" >&2; exit 1; }

python3 - "${SRC}" "${DEST}" "${OUTPUT_ROOT}" "${INPUT_ROOT}" <<'PY'
import os, shutil, sys
src, dest, out_root, in_root = sys.argv[1:]

def within(root, path):
    try:
        return os.path.commonpath((os.path.realpath(root), os.path.realpath(path))) == os.path.realpath(root)
    except ValueError:
        return False

if not within(out_root, src):
    sys.exit(f"src escapes output root: {src}")
os.makedirs(os.path.dirname(dest), exist_ok=True)
if os.path.islink(dest):
    os.unlink(dest)
shutil.copy2(src, dest)
if os.path.islink(dest):
    os.unlink(dest)
    sys.exit(f"refusing symlink dest {dest}")
if not within(in_root, dest):
    os.remove(dest)
    sys.exit(f"dest escapes input root: {dest}")
print(f"Vesta stage: copied {os.path.realpath(src)} -> {os.path.realpath(dest)}")
print(f"size_bytes={os.path.getsize(dest)}")
PY
