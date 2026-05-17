#!/usr/bin/env python3
"""
generate_manifest.py — Regenerate data/syllabus/content_manifest.json

Run from the production/ directory:

    python scripts/generate_manifest.py
    python scripts/generate_manifest.py --syllabus-dir ./data/syllabus

Scans all metadata.json files in the syllabus directory tree and writes
content_manifest.json mapping each folder_key to its relative physical path.

Fails loudly (non-zero exit) if:
  - Duplicate folder_key values are detected across metadata.json files
  - Any metadata.json has a missing or empty folder_key field
  - The syllabus directory does not exist

Run this script whenever you:
  - Add a new course folder
  - Rename an existing course folder (update metadata.json first)
  - Change a folder_key (coordinate with database migration for entitlements)

The generated manifest is committed to version control and validated at
container startup by ext_syllabus.py. Always commit it alongside any
metadata.json changes.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone


SCHEMA_VERSION = "1"
CONTENT_VERSION = "2026.05"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate content_manifest.json from metadata.json files"
    )
    parser.add_argument(
        "--syllabus-dir",
        default="./data/syllabus",
        help="Path to syllabus root directory (default: ./data/syllabus)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without writing the file",
    )
    args = parser.parse_args()

    syllabus_dir = Path(args.syllabus_dir).resolve()
    if not syllabus_dir.is_dir():
        print(
            f"ERROR: Syllabus directory not found: {syllabus_dir}",
            file=sys.stderr,
        )
        return 1

    manifest_path = syllabus_dir / "content_manifest.json"

    # Discover all metadata.json files anywhere under syllabus_dir.
    # Convention: they sit exactly at the course-folder level
    # (exam_folder/course_folder/metadata.json).
    found: dict[str, str] = {}   # folder_key → rel_path (POSIX slashes)
    errors: list[str] = []

    for meta_file in sorted(syllabus_dir.rglob("metadata.json")):
        rel_dir = meta_file.parent.relative_to(syllabus_dir)
        rel_str = rel_dir.as_posix()   # always forward-slash, even on Windows

        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid JSON in {rel_str}/metadata.json: {exc}")
            continue

        folder_key = data.get("folder_key", "").strip()
        if not folder_key:
            errors.append(f"Missing or empty folder_key in {rel_str}/metadata.json")
            continue

        if folder_key in found:
            errors.append(
                f"Duplicate folder_key '{folder_key}': "
                f"already at '{found[folder_key]}', also found at '{rel_str}'"
            )
            continue

        # Verify internal consistency: metadata.json folder_key must match
        # the relative path we computed (advisory — warns, doesn't block).
        folder_name = data.get("folder", "").strip()
        declared_path = rel_str.split("/")[-1]  # last segment of the path
        if folder_name and folder_name != declared_path:
            print(
                f"  WARNING: {rel_str}/metadata.json folder='{folder_name}' "
                f"does not match directory name '{declared_path}'",
                file=sys.stderr,
            )

        found[folder_key] = rel_str

    if errors:
        print("ERRORS detected — manifest NOT written:", file=sys.stderr)
        for err in errors:
            print(f"  ✗ {err}", file=sys.stderr)
        return 1

    if not found:
        print(
            "WARNING: No metadata.json files found — manifest will be empty.",
            file=sys.stderr,
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_version": CONTENT_VERSION,
        "folders": dict(sorted(found.items())),
    }

    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)

    if args.dry_run:
        print("--- DRY RUN: would write to", manifest_path, "---")
        print(manifest_json)
        return 0

    manifest_path.write_text(manifest_json + "\n", encoding="utf-8")

    print(f"✓ content_manifest.json written with {len(found)} folder(s):")
    for key, path in sorted(found.items()):
        print(f"    {key:30s} → {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
