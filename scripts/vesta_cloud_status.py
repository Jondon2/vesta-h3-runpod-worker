#!/usr/bin/env python3
"""Print the phone-readable Vesta cloud-production status without mutating it."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vesta_cloud_orchestrator import dashboard_markdown, load_state  # noqa: E402


if __name__ == "__main__":
    print(dashboard_markdown(load_state()), end="")
