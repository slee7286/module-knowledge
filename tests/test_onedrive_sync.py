from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_onedrive.py"
DEFAULT_DESTINATION = "/home/siheon/projects/OneDrive"


def fake_rclone(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "rclone"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['RCLONE_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    capture = tmp_path / "args.json"
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["RCLONE_CAPTURE"] = str(capture)
    return capture, env


def run_script(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_copy_uses_checksum_and_default_destination_without_deleting(tmp_path: Path) -> None:
    capture, env = fake_rclone(tmp_path)

    result = run_script(
        "onedrive:Year 2", "--exclude", "*.mp4", "--dry-run", env=env
    )

    assert result.returncode == 0, result.stderr
    args = json.loads(capture.read_text(encoding="utf-8"))
    assert args == [
        "copy",
        "onedrive:Year 2",
        DEFAULT_DESTINATION,
        "--checksum",
        "--progress",
        "--create-empty-src-dirs",
        "--exclude",
        "*.mp4",
        "--dry-run",
    ]
    assert "sync" not in args
    assert not any("delete" in arg for arg in args)


def test_dry_run_passes_through_and_uses_requested_destination(tmp_path: Path) -> None:
    capture, env = fake_rclone(tmp_path)
    destination = tmp_path / "local mirror"

    result = run_script(
        "onedrive:Year 2",
        "--destination",
        str(destination),
        "--dry-run",
        env=env,
    )

    assert result.returncode == 0, result.stderr
    args = json.loads(capture.read_text(encoding="utf-8"))
    assert args == [
        "copy",
        "onedrive:Year 2",
        str(destination),
        "--checksum",
        "--progress",
        "--create-empty-src-dirs",
        "--dry-run",
    ]
    assert not destination.exists()


def test_whole_remote_requires_explicit_allow_all(tmp_path: Path) -> None:
    capture, env = fake_rclone(tmp_path)

    result = run_script("onedrive:", env=env)

    assert result.returncode == 2
    assert "--all" in result.stderr
    assert not capture.exists()


def test_allows_whole_remote_when_explicitly_confirmed(tmp_path: Path) -> None:
    capture, env = fake_rclone(tmp_path)

    result = run_script("--all", "onedrive:", env=env)

    assert result.returncode == 0, result.stderr
    args = json.loads(capture.read_text(encoding="utf-8"))
    assert args[:3] == ["copy", "onedrive:", DEFAULT_DESTINATION]
