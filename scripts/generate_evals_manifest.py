#!/usr/bin/env python3
"""
Utility script to generate or update evals-manifest.json based on contents of ./evals/.
Scans for files matching *_summary.json and creates a manifest with path and name (timestamp).
"""

import json
import os
from datetime import datetime


def generate_manifest(evals_dir="./evals", manifest_path="./evals/evals-manifest.json"):
    """Generate manifest from JSON files in evals_dir."""
    manifest = []
    for filename in os.listdir(evals_dir):
        if filename.endswith("_summary.json"):
            timestamp_str = filename.split("_")[0]  # Extract YYYYMMDD_HHMMSS
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
        f"✅ Manifest generated/updated at {manifest_path} with {len(manifest)} entries."
    )


if __name__ == "__main__":
    generate_manifest()
