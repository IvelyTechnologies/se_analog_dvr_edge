"""Register Analog DVR publisher paths in an existing MediaMTX configuration."""
from __future__ import annotations
import re
import shutil
from pathlib import Path
from typing import Iterable

_STREAM_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

def ensure_publisher_paths(stream_names: Iterable[str], config_path: str | Path) -> list[str]:
    """Add missing publisher paths without changing existing MediaMTX entries."""
    names = list(dict.fromkeys(str(name).strip() for name in stream_names if str(name).strip()))
    for name in names:
        if not _STREAM_NAME.fullmatch(name):
            raise ValueError(f"invalid MediaMTX path name: {name!r}")

    path = Path(config_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    paths_start = next((index for index, line in enumerate(lines)
                        if re.fullmatch(r"paths:\s*(?:#.*)?\n?", line)), None)
    if paths_start is None:
        raise ValueError(f"MediaMTX config has no top-level paths: section: {path}")

    paths_end = len(lines)
    for index in range(paths_start + 1, len(lines)):
        line = lines[index]
        if line.strip() and not line.startswith((" ", "\t", "#")):
            paths_end = index
            break

    # Do not use a regex which includes ``\s`` here: it can consume a line
    # ending and make CRLF/LF MediaMTX configurations behave differently.
    # A path declaration is an indented, valid stream name ending with ':'.
    existing: set[str] = set()
    for line in lines[paths_start + 1 : paths_end]:
        if not line.startswith((" ", "\t")):
            continue
        candidate = line.strip()
        if not candidate.endswith(":"):
            continue
        candidate = candidate[:-1].strip()
        if _STREAM_NAME.fullmatch(candidate):
            existing.add(candidate)
    missing = [name for name in names if name not in existing]
    if not missing:
        return []

    insertion = []
    if paths_end > paths_start + 1 and lines[paths_end - 1].strip():
        insertion.append("\n")
    for name in missing:
        insertion.extend((f"  {name}:\n", "    source: publisher\n"))

    updated = lines[:paths_end] + insertion + lines[paths_end:]
    backup = path.with_name(f"{path.name}.before-analog-dvr")
    if not backup.exists():
        shutil.copy2(path, backup)
    temporary = path.with_name(f"{path.name}.analog-dvr.tmp")
    temporary.write_text("".join(updated), encoding="utf-8")
    temporary.replace(path)
    return missing
