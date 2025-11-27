#!/usr/bin/env python3

import os

"""
Utility script to generate or update evals-manifest.json based on contents of ./evals/.
Scans for files matching *_summary.json and creates a manifest with path and name (timestamp).
"""

import json
from datetime import datetime

import re


def generate_manifest(evals_dir="./evals", manifest_path="./evals/evals-manifest.json"):
    """Generate manifest from JSON files in evals_dir matching new pattern."""
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    evals_dir = os.path.join(ROOT_DIR, evals_dir)
    manifest_path = os.path.join(ROOT_DIR, manifest_path)
    manifest = []
    timestamp_pattern = re.compile(
        r"^(\d{8}_\d{6})_summary\.json$"
    )  # Matches YYYYMMDD_HHMMSS_summary.json

    for filename in os.listdir(evals_dir):
        match = timestamp_pattern.match(filename)
        if match:
            timestamp_str = match.group(1)  # e.g., 20251118_160840
            try:
                # Parse YYYYMMDD_HHMMSS
                dt = datetime.strptime(timestamp_str.replace("_", ""), "%Y%m%d%H%M%S")
                name = dt.strftime("%Y-%m-%d %H:%M:%S")  # Display format
            except ValueError:
                name = filename
            manifest.append({"path": f"./evals/{filename}", "name": name})

    # Sort by parsed datetime descending
    manifest.sort(
        key=lambda x: datetime.strptime(x["name"], "%Y-%m-%d %H:%M:%S"), reverse=True
    )

    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"✅ Manifest generated/updated at {manifest_path} with {len(manifest)} entries."
    )


if __name__ == "__main__":
    generate_manifest()
