#!/usr/bin/env python3
"""Incrementally copy a configured rclone OneDrive path to a local directory."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_DESTINATION = Path("/home/siheon/projects/OneDrive")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy new or changed files from an authenticated rclone remote. "
            "Existing destination-only files are never deleted."
        )
    )
    parser.add_argument(
        "source",
        help="rclone path such as 'onedrive:Year 2'; the account root needs --all",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
        help=f"local copy directory (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="explicitly permit copying the entire remote account root",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show planned transfers without downloading files",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="rclone exclusion pattern; may be repeated (for example '*.mp4')",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    remote, separator, remote_path = args.source.partition(":")
    if not separator or not remote:
        parser.error("source must be an rclone remote path such as 'onedrive:Year 2'")

    is_remote_root = not remote_path.strip("/")
    if is_remote_root and not args.all:
        parser.error(
            "copying an entire OneDrive account requires --all; "
            "otherwise specify a folder such as 'onedrive:Year 2'"
        )
    if args.all and not is_remote_root:
        parser.error("--all is only valid with a remote root such as 'onedrive:'")

    rclone = shutil.which("rclone")
    if rclone is None:
        print(
            "rclone is required. Install it (for example, 'sudo apt install rclone'), "
            "then configure a OneDrive remote with 'rclone config'.",
            file=sys.stderr,
        )
        return 127

    destination = args.destination.expanduser()
    if not args.dry_run:
        destination.mkdir(parents=True, exist_ok=True)
    command = [
        rclone,
        "copy",
        args.source,
        str(destination),
        "--checksum",
        "--progress",
        "--create-empty-src-dirs",
    ]
    for pattern in args.exclude:
        command.extend(["--exclude", pattern])
    if args.dry_run:
        command.append("--dry-run")

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
