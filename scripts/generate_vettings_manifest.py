#!/usr/bin/env python3
"""
Utility script to generate or update vettings-manifest.json based on contents of ./evals/.
Scans for files matching *_summary_dao*_vetting.json and creates a manifest with path and name (timestamp).
"""

import json
import os
import re
from datetime import datetime


def generate_manifest(evals_dir="./evals", manifest_path="./evals/vettings-manifest.json"):
    """Generate manifest from vetting summary JSON files in evals_dir."""
    manifest = []
    timestamp_pattern = re.compile(r"^(\d{8}_\d{6})_summary_dao.*_vetting\.json$")
    for filename in os.listdir(evals_dir):
        match = timestamp_pattern.match(filename)
        if match:
            timestamp_str = match.group(1)  # YYYYMMDD_HHMMSS
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                name = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                name = filename
            manifest.append({"path": f"./evals/{filename}", "name": name})

    # Sort by timestamp descending
    manifest.sort(key=lambda x: x["name"], reverse=True)

    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"✅ Vettings manifest generated/updated at {manifest_path} with {len(manifest)} entries."
    )


if __name__ == "__main__":
    generate_manifest()
