#!/usr/bin/env python3
"""Bounded, fail-closed controller for Vesta's 12-post production.

This program is intentionally a single-iteration controller.  GitHub Actions
invokes it on a schedule or from the phone-triggered workflow_dispatch form;
it records state and exits rather than holding an infinite runner open.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "production/cloud_state.json"
ASSIGNMENT_PATH = ROOT / "production/12post_20260930/assignment.json"
ASTRA_RUNNER = ROOT / "production/12post_20260930/run_astra_post005_pair_qc.py"
RENDER_RUNNER = ROOT / "scripts/vesta_cloud_render.py"
REPORTS_DIR = ROOT / "production/12post_20260930/reports"
DASHBOARD_TITLE = "VESTA — 12 Post Production Board"
RELEASE_TAG = "vesta-production-artifacts"
STATE_NAMES = {
    "PREPARE", "RENDER_REQUIRED", "RENDERING", "RENDER_COMPLETE",
    "QC_REQUIRED", "QC_RUNNING", "QC_PASS", "REPAIR_REQUIRED", "LOCKED",
    "PREFLIGHT_REQUIRED", "PREFLIGHT_PASS", "MOTION_REQUIRED",
    "MOTION_RUNNING", "MOTION_QC", "UPSCALE", "WATERMARK", "FINAL_QC",
    "FINAL_READY", "BLOCKED",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    return (value or now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def pair_template(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "prepared": False,
        "rendered": False,
        "qc_status": "PENDING",
        "locked": False,
        "revision": None,
        "critical": None,
        "major": None,
        "artifact_location": None,
        "qc_report": None,
        "rate_limit_count": 0,
        "next_qc_retry_at": None,
    }


def assignment_pair_names(post: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for detail in post.get("sequence", [])[1:5]:
        picture = detail.get("picture", "")
        match = re.search(r"BEFORE to AFTER:\s*([^.]*)", picture, re.I)
        names.append((match.group(1) if match else detail.get("name", "DETAIL")).strip())
    return names or ["DETAIL_1", "DETAIL_2", "DETAIL_3", "DETAIL_4"]


def lane_for(post_id: str) -> str:
    number = int(post_id.rsplit("_", 1)[1])
    if number == 5:
        return "LANE_A"
    if number <= 4:
        return "LANE_B"
    if number <= 8:
        return "LANE_C"
    return "LANE_D"


def default_post(post: dict[str, Any]) -> dict[str, Any]:
    post_id = post["post"]
    return {
        "post_id": post_id,
        "room": post.get("room", "UNSPECIFIED"),
        "target_duration": post.get("duration_sec"),
        "creative_status": "PREPARE",
        "technical_status": "NOT_STARTED",
        "lane": lane_for(post_id),
        "pairs": [pair_template(name) for name in assignment_pair_names(post)],
        "preflight_status": "PENDING",
        "motion_status": "WAIT",
        "watermark_status": "WAIT",
        "4k_status": "WAIT",
        "final_qc_status": "WAIT",
        "final_ready": False,
        "last_error": None,
        "updated_at": stamp(),
    }


def bootstrap_state(volume_id: str = "PENDING", data_center: str = "US-IL-1") -> dict[str, Any]:
    assignments = read_json(ASSIGNMENT_PATH)["posts"]
    posts = [default_post(post) for post in assignments]
    post5 = next(post for post in posts if post["post_id"] == "POST_005")
    post5["pairs"] = [pair_template(name) for name in ("LANTERN", "WOOL", "OAK", "GLASS")]
    glass = next(pair for pair in post5["pairs"] if pair["name"] == "GLASS")
    glass.update({
        "prepared": True, "rendered": True, "qc_status": "PASS", "locked": True,
        "revision": "stills_glass_r8_20261003_remote", "critical": 0, "major": 0,
        "artifact_location": {"provider": "runpod_volume", "path": "artifacts/POST_005/GLASS/stills_glass_r8_20261003_remote"},
        "qc_report": "production/12post_20260930/reports/POST_005_astra_glass_v4_r8_20261003_detail_qc.json",
    })
    lantern = next(pair for pair in post5["pairs"] if pair["name"] == "LANTERN")
    lantern.update({
        "prepared": True, "rendered": True, "qc_status": "RATE_LIMITED", "locked": False,
        "revision": "stills_lantern_r13_20261003_remote", "critical": None, "major": None,
        "artifact_location": {
            "provider": "github_release", "release_tag": RELEASE_TAG,
            "before_asset": "LANTERN_BEFORE.png",
            "after_asset": "LANTERN_AFTER.png",
            "volume_path": "artifacts/POST_005/LANTERN/stills_lantern_r13_20261003_remote",
        },
        "rate_limit_count": 1,
        "next_qc_retry_at": stamp(now() + timedelta(minutes=5)),
        "last_error": "ASTRA_HTTP_429: candidate preserved; retry QC only, do not rerender.",
    })
    post5.update({
        "creative_status": "QC_REQUIRED", "technical_status": "NOT_STARTED",
        "preflight_status": "PENDING", "motion_status": "WAIT", "watermark_status": "WAIT",
        "4k_status": "WAIT", "final_qc_status": "WAIT", "final_ready": False,
        "last_error": lantern["last_error"], "updated_at": stamp(),
        "render_specs": {
            "WOOL": {"mode": "wool", "builder": "production/12post_20260930/delivery/POST_005/v4/build_scene.py"},
            "OAK": {"mode": "oak", "builder": "production/12post_20260930/delivery/POST_005/v4/build_scene.py"},
        },
    })
    return {
        "schema_version": 1,
        "updated_at": stamp(),
        "controller": {
            "state": "ACTIVE", "stop_requested": False, "iteration": 0,
            "max_gpu_workers": 1,
            "required_secret_names": ["RUNPOD_API_KEY", "OPENAI_API_KEY"],
            "missing_github_secret_names": ["RUNPOD_API_KEY", "OPENAI_API_KEY"],
            "github_secret_check_at": stamp(),
            "quality_gate": "CRITICAL=0 and MAJOR=0 are mandatory for every lock and final.",
        },
        "artifacts": {
            "source_provider": "runpod_network_volume", "volume_id": volume_id,
            "data_center_id": data_center, "root_path": "/workspace/vesta-v12",
            "source_assets": "assets/blender", "post005_support": "production/POST_005/v4",
            "render_outputs": "artifacts", "release_tag": RELEASE_TAG,
            "manifest": "production/cloud_asset_manifest.json",
            "remote_asset_status": "PASS",
            "missing_required_assets": 0,
            "blender": "5.2.2 LTS", "cycles_gpu": "PASS",
        },
        "dashboard": {"title": DASHBOARD_TITLE, "issue_number": None, "url": None},
        "posts": posts,
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        raise SystemExit(f"missing state: {STATE_PATH}; run with --bootstrap first")
    return read_json(STATE_PATH)


def post_by_id(state: dict[str, Any], post_id: str) -> dict[str, Any]:
    for post in state["posts"]:
        if post["post_id"] == post_id:
            return post
    raise KeyError(post_id)


def pair_by_name(post: dict[str, Any], name: str) -> dict[str, Any]:
    for pair in post["pairs"]:
        if pair["name"] == name:
            return pair
    raise KeyError(name)


def locked_count(post: dict[str, Any]) -> int:
    return sum(bool(pair.get("locked")) for pair in post["pairs"])


def retry_due(pair: dict[str, Any]) -> bool:
    retry_at = parse_time(pair.get("next_qc_retry_at"))
    return retry_at is None or retry_at <= now()


def set_rate_limited(post: dict[str, Any], pair: dict[str, Any], reason: str) -> None:
    count = int(pair.get("rate_limit_count") or 0) + 1
    delay_seconds = min(3600, 300 * (2 ** max(0, count - 1)))
    pair.update({
        "qc_status": "RATE_LIMITED", "locked": False, "critical": None, "major": None,
        "rate_limit_count": count,
        "next_qc_retry_at": stamp(now() + timedelta(seconds=delay_seconds)),
        "last_error": reason,
    })
    post.update({"creative_status": "QC_REQUIRED", "last_error": reason, "updated_at": stamp()})


def required_runtime_secrets(state: dict[str, Any]) -> list[str]:
    return [name for name in state["controller"]["required_secret_names"] if not os.environ.get(name, "").strip()]


def run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(f"{command[0]}: {message}")
    return result


def run_existing_astra(state: dict[str, Any], post: dict[str, Any], pair: dict[str, Any], repo: str) -> None:
    """QC an existing release-backed candidate.  429 is deliberately non-failing."""
    if not retry_due(pair):
        return
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        post.update({"creative_status": "BLOCKED", "last_error": "MISSING_GITHUB_SECRET: OPENAI_API_KEY", "updated_at": stamp()})
        return
    artifact = pair.get("artifact_location") or {}
    if artifact.get("provider") != "github_release":
        post.update({"creative_status": "BLOCKED", "last_error": "QC_ARTIFACT_UNAVAILABLE", "updated_at": stamp()})
        return
    pair["qc_status"] = "QC_RUNNING"
    post["creative_status"] = "QC_RUNNING"
    with tempfile.TemporaryDirectory(prefix="vesta-qc-") as temporary:
        temporary_path = Path(temporary)
        try:
            for asset in (artifact["before_asset"], artifact["after_asset"]):
                run(["gh", "release", "download", artifact["release_tag"], "--repo", repo, "--pattern", asset, "--dir", str(temporary_path)])
        except RuntimeError as exc:
            post.update({"creative_status": "BLOCKED", "last_error": f"QC_ARTIFACT_UNAVAILABLE: {exc}", "updated_at": stamp()})
            pair["qc_status"] = "BLOCKED"
            return
        before = temporary_path / artifact["before_asset"]
        after = temporary_path / artifact["after_asset"]
        report = REPORTS_DIR / f"{post['post_id']}_astra_{pair['name'].lower()}_{pair['revision']}_cloud.json"
        result = run([sys.executable, str(ASTRA_RUNNER), "--pair", pair["name"], "--before", str(before), "--after", str(after), "--out", str(report)], check=False)
    document = read_json(report) if report.exists() else {}
    if document.get("http") == 429:
        set_rate_limited(post, pair, "ASTRA_HTTP_429: candidate preserved; retry QC only, do not rerender.")
        return
    parsed = document.get("parsed") or {}
    if not document.get("ok"):
        post.update({"creative_status": "QC_REQUIRED", "last_error": "ASTRA_UNAVAILABLE", "updated_at": stamp()})
        pair["qc_status"] = "QC_REQUIRED"
        return
    critical, major = int(parsed.get("CRITICAL", 0)), int(parsed.get("MAJOR", 0))
    pair.update({"critical": critical, "major": major, "qc_report": str(report.relative_to(ROOT)), "next_qc_retry_at": None})
    if parsed.get(f"{pair['name']}_PAIR_QC") == "PASS" and critical == 0 and major == 0:
        pair.update({"qc_status": "PASS", "locked": True})
        post["last_error"] = None
    else:
        pair.update({"qc_status": "FAIL", "locked": False})
        post.update({"creative_status": "REPAIR_REQUIRED", "last_error": "ASTRA_QC_FAIL: targeted repair required"})
    post["updated_at"] = stamp()


def next_revision(pair: dict[str, Any]) -> str:
    """Choose a new V4 directory; historical output names are never reused."""
    date = now().strftime("%Y%m%d")
    base = f"stills_{pair['name'].lower()}_cloud_{date}"
    previous = str(pair.get("revision") or "")
    return base if base != previous else f"{base}_r2"


def render_post005_pair(state: dict[str, Any], post: dict[str, Any], pair: dict[str, Any], repo: str) -> None:
    """Dispatch one approved pair, then immediately return to bounded QC work."""
    missing = required_runtime_secrets(state)
    if missing:
        post.update({
            "creative_status": "BLOCKED",
            "last_error": "MISSING_GITHUB_SECRET: " + ", ".join(missing),
            "updated_at": stamp(),
        })
        return
    if os.environ.get("VESTA_EXECUTE_GPU", "") != "1":
        post.update({"creative_status": "RENDER_REQUIRED", "next_action": f"Render {pair['name']} only", "updated_at": stamp()})
        return
    volume_id = str(state["artifacts"].get("volume_id", "PENDING"))
    if not volume_id or volume_id == "PENDING":
        post.update({"creative_status": "BLOCKED", "last_error": "MISSING_RUNPOD_VOLUME", "updated_at": stamp()})
        return
    revision = next_revision(pair)
    pair.update({"prepared": True, "qc_status": "RENDERING", "locked": False, "revision": revision})
    post.update({"creative_status": "RENDERING", "last_error": None, "updated_at": stamp()})
    result = run([
        sys.executable, str(RENDER_RUNNER), "--pair", pair["name"], "--revision", revision,
        "--volume-id", volume_id, "--data-center", str(state["artifacts"].get("data_center_id", "US-IL-1")),
        "--repo", repo,
    ], check=False)
    if result.returncode:
        pair["qc_status"] = "RENDER_REQUIRED"
        post.update({"creative_status": "RENDER_REQUIRED", "last_error": "RUNPOD_RENDER_FAILED", "updated_at": stamp()})
        return
    try:
        document = json.loads(result.stdout.strip().splitlines()[-1])
        artifact = document["artifact_location"]
    except (IndexError, json.JSONDecodeError, KeyError):
        pair["qc_status"] = "RENDER_REQUIRED"
        post.update({"creative_status": "RENDER_REQUIRED", "last_error": "RUNPOD_RENDER_ARTIFACT_UNVERIFIED", "updated_at": stamp()})
        return
    pair.update({
        "rendered": True, "qc_status": "QC_REQUIRED", "artifact_location": artifact,
        "critical": None, "major": None, "next_qc_retry_at": stamp(),
    })
    post.update({"creative_status": "QC_REQUIRED", "next_action": f"Run Astra QC for {pair['name']} {revision}", "updated_at": stamp()})


def advance_post005(post: dict[str, Any]) -> None:
    """Advance only from a completed, valid pair lock; never infer a final."""
    lantern, wool, oak, glass = (pair_by_name(post, name) for name in ("LANTERN", "WOOL", "OAK", "GLASS"))
    if post.get("creative_status") == "BLOCKED" and str(post.get("last_error", "")).startswith("MISSING_GITHUB_SECRET"):
        post["updated_at"] = stamp()
        return
    active_pairs = (lantern, wool, oak)
    failed = next((pair for pair in active_pairs if pair.get("qc_status") == "FAIL"), None)
    if failed:
        post.update({"creative_status": "REPAIR_REQUIRED", "next_action": f"Create targeted {failed['name']} repair from Astra findings"})
        post["updated_at"] = stamp()
        return
    limited = next((pair for pair in active_pairs if pair.get("qc_status") == "RATE_LIMITED"), None)
    if limited:
        post.update({"creative_status": "QC_REQUIRED", "next_action": f"Retry Astra QC for {limited['name']} {limited.get('revision')}"})
        post["updated_at"] = stamp()
        return
    if not glass.get("locked"):
        post.update({"creative_status": "BLOCKED", "last_error": "GLASS_LOCK_REQUIRED"})
    elif lantern.get("locked") and not wool.get("locked"):
        wool["prepared"] = True
        post.update({"creative_status": "RENDER_REQUIRED", "last_error": None, "next_action": "Render WOOL only"})
    elif lantern.get("locked") and wool.get("locked") and not oak.get("locked"):
        oak["prepared"] = True
        post.update({"creative_status": "RENDER_REQUIRED", "last_error": None, "next_action": "Render OAK only"})
    elif all(pair.get("locked") for pair in (lantern, wool, oak, glass)):
        post.update({"creative_status": "PREFLIGHT_REQUIRED", "next_action": "Run POST_005 creative preflight"})
    else:
        post.setdefault("next_action", "Retry LANTERN QC or make Astra-directed repair")
    post["updated_at"] = stamp()


def prepare_other_lanes(state: dict[str, Any]) -> None:
    """Bounded, no-GPU manifest preparation for the other eleven posts."""
    for post in state["posts"]:
        if post["post_id"] == "POST_005" or post["creative_status"] != "PREPARE":
            continue
        for pair in post["pairs"]:
            pair["prepared"] = True
        post.update({
            "creative_status": "RENDER_REQUIRED",
            "preparation_status": "PASS",
            "next_action": "Create an approved render spec before GPU dispatch",
            "updated_at": stamp(),
        })


def process_iteration(state: dict[str, Any], command: str, repo: str) -> None:
    controller = state["controller"]
    if command == "stop":
        controller.update({"state": "STOPPED", "stop_requested": True})
        for post in state["posts"]:
            if post["creative_status"] in {"RENDERING", "MOTION_RUNNING"}:
                post["last_error"] = "STOP_REQUESTED: active remote work must be recorded before termination"
                post["updated_at"] = stamp()
        return
    if command == "resume":
        controller.update({"state": "ACTIVE", "stop_requested": False})
    if controller.get("stop_requested") and command not in {"status", "retry_failed"}:
        return
    if command == "retry_failed":
        for post in state["posts"]:
            for pair in post["pairs"]:
                if pair.get("qc_status") == "RATE_LIMITED":
                    pair["next_qc_retry_at"] = stamp()
    target = None
    if command.startswith("post_"):
        target = "POST_" + command.rsplit("_", 1)[1].zfill(3)
    post5 = post_by_id(state, "POST_005")
    lantern = pair_by_name(post5, "LANTERN")
    if command in {"resume", "retry_failed", "post_005"} and (target in {None, "POST_005"}):
        if lantern.get("qc_status") == "RATE_LIMITED":
            run_existing_astra(state, post5, lantern, repo)
        advance_post005(post5)
        if post5.get("creative_status") == "RENDER_REQUIRED":
            wool, oak = (pair_by_name(post5, name) for name in ("WOOL", "OAK"))
            candidate = wool if lantern.get("locked") and not wool.get("locked") else oak if wool.get("locked") and not oak.get("locked") else None
            if candidate and not candidate.get("rendered"):
                render_post005_pair(state, post5, candidate, repo)
        for pair in post5["pairs"]:
            if pair.get("qc_status") == "QC_REQUIRED" and pair.get("rendered") and (pair.get("artifact_location") or {}).get("provider") == "github_release":
                run_existing_astra(state, post5, pair, repo)
                break
        advance_post005(post5)
    if command == "resume":
        prepare_other_lanes(state)
    controller["iteration"] = int(controller.get("iteration", 0)) + 1
    state["updated_at"] = stamp()


def dashboard_markdown(state: dict[str, Any]) -> str:
    rows = [
        "# VESTA — 12 Post Production Board",
        "",
        "Cloud controller: bounded GitHub Actions iterations. A rate limit preserves the candidate and queues QC; it never becomes a creative failure.",
        "",
        "| POST | PREP | PAIRS | QC | MOTION | 4K | FINAL | BLOCKER |",
        "|---|---|---|---|---|---|---|---|",
    ]
    total_final = total_rendering = total_qc = total_blocked = 0
    for post in state["posts"]:
        pairs = f"{locked_count(post)}/{len(post['pairs'])} LOCKED"
        qc = next((pair["qc_status"] for pair in post["pairs"] if pair.get("qc_status") not in {"PASS", "PENDING"}), "WAIT")
        prep = "PASS" if post.get("preparation_status") == "PASS" or all(pair.get("prepared") for pair in post["pairs"]) else "WAIT"
        final = "YES" if post.get("final_ready") else "NO"
        blocker = (post.get("last_error") or "—").replace("|", "/")[:100]
        rows.append(f"| {post['post_id']} | {prep} | {pairs} | {qc} | {post.get('motion_status', 'WAIT')} | {post.get('4k_status', 'WAIT')} | {final} | {blocker} |")
        total_final += int(bool(post.get("final_ready")))
        total_rendering += int(post.get("creative_status") in {"RENDERING", "MOTION_RUNNING"})
        total_qc += int(post.get("creative_status") in {"QC_REQUIRED", "QC_RUNNING"})
        total_blocked += int(post.get("creative_status") == "BLOCKED")
    rows.extend([
        "",
        f"**TOTAL_FINAL_READY:** {total_final}/12  ",
        f"**TOTAL_RENDERING:** {total_rendering}  ",
        f"**TOTAL_QC:** {total_qc}  ",
        f"**TOTAL_BLOCKED:** {total_blocked}",
        "",
        f"Updated: {state['updated_at']}",
    ])
    return "\n".join(rows) + "\n"


def update_dashboard_issue(state: dict[str, Any], repo: str) -> None:
    """Create once, then edit the same phone-readable issue using GH_TOKEN."""
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        return
    body = dashboard_markdown(state)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as temporary:
        temporary.write(body)
        body_path = Path(temporary.name)
    try:
        dashboard = state["dashboard"]
        issue_number = dashboard.get("issue_number")
        if not issue_number:
            listed = run(["gh", "issue", "list", "--repo", repo, "--state", "all", "--search", f'"{DASHBOARD_TITLE}" in:title', "--json", "number,title,url"], check=False)
            matches = json.loads(listed.stdout or "[]")
            exact = next((item for item in matches if item.get("title") == DASHBOARD_TITLE), None)
            if exact:
                issue_number, dashboard["url"] = exact["number"], exact["url"]
            else:
                created = run(["gh", "issue", "create", "--repo", repo, "--title", DASHBOARD_TITLE, "--body-file", str(body_path)])
                dashboard["url"] = created.stdout.strip()
                issue_number = int(dashboard["url"].rstrip("/").rsplit("/", 1)[1])
            dashboard["issue_number"] = issue_number
        run(["gh", "issue", "edit", str(issue_number), "--repo", repo, "--body-file", str(body_path)])
    finally:
        body_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", default="status", choices=["resume", "status", "stop", "retry_failed"] + [f"post_{number:03d}" for number in range(1, 13)])
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--volume-id", default=os.environ.get("VESTA_ASSET_VOLUME_ID", "PENDING"))
    parser.add_argument("--data-center", default=os.environ.get("VESTA_ASSET_DATA_CENTER", "US-IL-1"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--update-dashboard", action="store_true")
    args = parser.parse_args()
    if args.bootstrap:
        state = bootstrap_state(args.volume_id, args.data_center)
        write_json(STATE_PATH, state)
    state = load_state()
    if args.volume_id != "PENDING":
        state["artifacts"].update({"volume_id": args.volume_id, "data_center_id": args.data_center})
    if args.command != "status":
        process_iteration(state, args.command, args.repo)
    missing = required_runtime_secrets(state)
    state["controller"]["missing_runtime_secret_names"] = missing
    state["updated_at"] = stamp()
    if args.update_dashboard and args.repo:
        update_dashboard_issue(state, args.repo)
    write_json(STATE_PATH, state)
    print(dashboard_markdown(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
