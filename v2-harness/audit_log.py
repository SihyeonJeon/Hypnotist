"""Append-only audit log with SHA-256 evidence hashing."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

_BUF_SIZE = 65536


def hash_file(path: str | os.PathLike, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_BUF_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class AuditLog:
    def __init__(self, log_path: str | os.PathLike) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self._path, "a")

    def record(
        self,
        event: str,
        *,
        operator: str,
        target: str | None = None,
        artifact_path: str | os.PathLike | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "epoch": time.time(),
            "event": event,
            "operator": operator,
        }
        if target is not None:
            entry["target"] = target
        if artifact_path is not None:
            p = Path(artifact_path)
            entry["artifact"] = str(p)
            if p.exists():
                entry["sha256"] = hash_file(p)
        if extra:
            entry["extra"] = extra

        line = json.dumps(entry, separators=(",", ":"))
        self._fd.write(line + "\n")
        self._fd.flush()
        return entry

    def close(self) -> None:
        self._fd.close()
