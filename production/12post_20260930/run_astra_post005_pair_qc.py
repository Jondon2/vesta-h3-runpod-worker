#!/usr/bin/env python3
"""Pixel-grounded Astra pair QC for preserved POST_005 V4 render revisions."""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


PROJECT = "proj_3usdgXS4YshxX2CI3xKqTZAX"


def api_key() -> str:
    # GitHub Actions supplies this through an Actions secret.  Local execution
    # retains the existing Keychain lookup and never prints either value.
    from_env = os.environ.get("OPENAI_API_KEY", "").strip()
    if from_env:
        return from_env
    raw = subprocess.check_output(
        ["security", "find-generic-password", "-s", "Vesta Astra", "-a", "OPENAI_API_KEY", "-w"],
        stderr=subprocess.DEVNULL,
    )
    return raw.decode().strip()


def data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return response["output_text"]
    return "\n".join(
        item.get("text", "")
        for output in response.get("output", [])
        if isinstance(output, dict)
        for item in output.get("content", [])
        if isinstance(item, dict) and item.get("type") in {"output_text", "text"}
    )


def parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


def prompt(pair: str) -> str:
    if pair == "GLASS":
        return """VESTA POST_005 V4 — ASTRA PIXEL QC. Inspect the two attached render pixels only.

Image 1 is GLASS_BEFORE and image 2 is GLASS_AFTER. They must depict precisely the same
evening-bedroom window-detail camera and geometry. This is intentionally a tight glazing shot:
ROOM_MATCH means that the locked mullion, pane layout, city perspective, and light positions remain
the same without evidence of a different room or inserted scene. Do not fail ROOM_MATCH merely
because the wider bed, chest, or other furnishings are outside this detail framing. Both must be
premium, physically rendered, and attractive.
They differ only in the locked architectural glazing:
- BEFORE: 6 mm glass, IOR 1.45, roughness 0.055; subtly broader, believable city transmission.
- AFTER: 6 mm glass, IOR 1.52, roughness 0.025; visibly cleaner city building edges, point lights,
  and microcontrast, while retaining the same city composition and perspective.

The physical reflection requirement is strict: no hard peach paper-lantern silhouette or flat
peach disk. A real internal bulb may make only a small, soft, physically integrated highlight in
the glazing. No fake/composited-looking reflection, mask edge, halo, or unrelated city replacement.

Return JSON only:
{
  "GLASS_PAIR_QC": "PASS | FAIL",
  "PHOTOREALISM": "PASS | FAIL",
  "MATERIAL_REALISM": "PASS | FAIL",
  "ROOM_MATCH": "PASS | FAIL",
  "TRANSMISSION_REALISM": "PASS | FAIL",
  "REFLECTION_INTEGRATION": "PASS | FAIL",
  "BEFORE_AFTER_CLARITY": "PASS | FAIL",
  "SAME_GEOMETRY": "PASS | FAIL",
  "TRANSITION_ALIGNMENT": "PASS | FAIL",
  "CRITICAL": 0,
  "MAJOR": 0,
  "MINOR": 0,
  "DEFECTS": ["pixel-grounded defects only"],
  "REPAIR_INSTRUCTIONS": "empty when PASS"
}

Set GLASS_PAIR_QC to PASS only if every named gate passes and CRITICAL and MAJOR are both zero.
Do not infer quality from filenames, request metadata, or this description; judge visible pixels.
"""
    if pair == "LANTERN":
        return """VESTA POST_005 V4 — ASTRA PIXEL QC. Inspect the two attached render pixels only.

Image 1 is LANTERN_BEFORE and image 2 is LANTERN_AFTER in the same locked detail camera,
room, tabletop, base, and cage registration. BEFORE must be a credible, simpler photographed
steel cage lantern: non-perfect metal construction, believable bevels/roughness, a physically
plausible bulb, mounting/base, contact shadow, and nearby light spill. AFTER must be a premium,
physically made thin-paper lantern in that same cage: a continuous smooth shade with no faceting;
visible fine shallow ribs and believable attachment collars; natural, non-repeating fibre/pigment
and thickness variation; and actual transmitted lighting from an internal bulb. The paper must
not be globally emissive, opaque tan plastic, a cutout, or a fake glow. The shade must sit
coherently inside the cage with no unexplained intersections; glass, bulb, socket, and support
assembly should resolve naturally where pixel scale permits. Judge pixels, not the stated intent.

Return JSON only:
{
  "LANTERN_PAIR_QC": "PASS | FAIL",
  "PHOTOREALISM": "PASS | FAIL",
  "MATERIAL_REALISM": "PASS | FAIL",
  "CONSTRUCTION_REALISM": "PASS | FAIL",
  "PAPER_REALISM": "PASS | FAIL",
  "RIB_REALISM": "PASS | FAIL",
  "TRANSMITTED_LIGHT_VARIATION": "PASS | FAIL",
  "REFLECTION_STATE_MATCH": "PASS | FAIL",
  "BEFORE_AFTER_CLARITY": "PASS | FAIL",
  "ROOM_MATCH": "PASS | FAIL",
  "SAME_GEOMETRY": "PASS | FAIL",
  "TRANSITION_ALIGNMENT": "PASS | FAIL",
  "CRITICAL": 0,
  "MAJOR": 0,
  "MINOR": 0,
  "DEFECTS": ["pixel-grounded defects only"],
  "REPAIR_INSTRUCTIONS": "empty when PASS"
}

Set LANTERN_PAIR_QC to PASS only if every named gate passes and CRITICAL and MAJOR are both
zero. Do not infer quality from filenames or request metadata; judge visible pixels.
"""
    focus = {
        "LANTERN": "The AFTER lantern must read as a physically made, smooth paper-and-glass lantern with fine ribs, natural translucency variation, internal support/bulb detail, and no faceting. BEFORE remains a credible simpler state; neither can contain a cutout, fake glow, or altered room/camera.",
        "WOOL": "The AFTER throw must read as believable oatmeal wool/boucle with visible fiber scale, pile variation, and drape. BEFORE remains a credible simpler linen state; no selective blur, mask edge, or geometry change is acceptable.",
        "OAK": "The AFTER chest must read as premium dark oak with real grain, pores, coherent roughness, and constructed drawer geometry. BEFORE remains a credible lighter oak state; no flat overlay, rectangular mask, or altered room/camera is acceptable.",
    }
    if pair not in focus:
        raise ValueError(f"unsupported pair: {pair}")
    return f"""VESTA POST_005 V4 — ASTRA PIXEL QC. Inspect the two attached render pixels only.

Image 1 is {pair}_BEFORE and image 2 is {pair}_AFTER in an intentionally tight same-room detail shot.
{focus[pair]}

Return JSON only:
{{
  "{pair}_PAIR_QC": "PASS | FAIL",
  "PHOTOREALISM": "PASS | FAIL",
  "MATERIAL_REALISM": "PASS | FAIL",
  "ROOM_MATCH": "PASS | FAIL",
  "DETAIL_REALISM": "PASS | FAIL",
  "BEFORE_AFTER_CLARITY": "PASS | FAIL",
  "SAME_GEOMETRY": "PASS | FAIL",
  "TRANSITION_ALIGNMENT": "PASS | FAIL",
  "CRITICAL": 0,
  "MAJOR": 0,
  "MINOR": 0,
  "DEFECTS": ["pixel-grounded defects only"],
  "REPAIR_INSTRUCTIONS": "empty when PASS"
}}

Set {pair}_PAIR_QC to PASS only if every named gate passes and CRITICAL and MAJOR are both zero.
Do not infer quality from filenames or request metadata; judge visible pixels.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.before, args.after):
        if not path.is_file():
            raise SystemExit(f"missing render: {path}")
    content = [
        {"type": "input_text", "text": prompt(args.pair)},
        {"type": "input_text", "text": f"IMAGE 1: {args.pair}_BEFORE"},
        {"type": "input_image", "image_url": data_url(args.before)},
        {"type": "input_text", "text": f"IMAGE 2: {args.pair}_AFTER"},
        {"type": "input_image", "image_url": data_url(args.after)},
    ]
    payload = {
        "model": "gpt-6-astra",
        "instructions": "You are Astra, Vesta's strict photorealism and continuity QC director. Return JSON only.",
        "input": [{"role": "user", "content": content}],
        "store": False,
        "max_output_tokens": 3000,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "OpenAI-Project": PROJECT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            raw = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"ok": False, "http": exc.code}, indent=2) + "\n")
        print(json.dumps({"ok": False, "http": exc.code}))
        return 1
    text = output_text(raw)
    parsed = parse_json(text)
    result = {"ok": bool(parsed), "pair": args.pair, "before": str(args.before), "after": str(args.after), "parsed": parsed, "text": text}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"ok": bool(parsed), "pair": args.pair, "qc": (parsed or {}).get(f"{args.pair}_PAIR_QC"), "critical": (parsed or {}).get("CRITICAL"), "major": (parsed or {}).get("MAJOR")}))
    return 0 if parsed else 2


if __name__ == "__main__":
    raise SystemExit(main())
