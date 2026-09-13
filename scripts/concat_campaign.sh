#!/usr/bin/env bash
# Join two Vesta campaign shots into one MP4 without changing duration.
# Prefer stream copy when both files share H.264 + timebase; re-encode only
# if copy fails. Does not start a GPU worker.
set -euo pipefail

usage() {
  echo "Usage: $0 <shot_a.mp4> <shot_b.mp4> <out.mp4>" >&2
  exit 2
}

[ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && usage
[ "$#" -eq 3 ] || usage

SHOT_A=$1
SHOT_B=$2
OUT=$3

command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null

for f in "$SHOT_A" "$SHOT_B"; do
  [ -s "$f" ] || { echo "missing or empty: $f" >&2; exit 1; }
done

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# Concat demuxer requires identical codecs for -c copy.
{
  printf "file '%s'\n" "$(cd "$(dirname "$SHOT_A")" && pwd)/$(basename "$SHOT_A")"
  printf "file '%s'\n" "$(cd "$(dirname "$SHOT_B")" && pwd)/$(basename "$SHOT_B")"
} > "${WORKDIR}/list.txt"

if ffmpeg -y -hide_banner -loglevel error \
  -f concat -safe 0 -i "${WORKDIR}/list.txt" \
  -c copy \
  "$OUT"
then
  echo "Vesta concat: stream-copied -> $OUT"
  ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
  exit 0
fi

echo "Vesta concat: copy failed; re-encoding with libx264 (still CPU, no GPU)" >&2
ffmpeg -y -hide_banner -loglevel error \
  -f concat -safe 0 -i "${WORKDIR}/list.txt" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium -movflags +faststart \
  -an \
  "$OUT"
echo "Vesta concat: re-encoded -> $OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
