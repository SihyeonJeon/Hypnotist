"""Scope guard for phase 2 internal VLAN assessment.

Rejects any target not within approved VLAN CIDR ranges and confines
all file writes to the engagement evidence directory.
"""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from typing import Sequence


class ScopeViolation(Exception):
    pass


class ScopeGuard:
    def __init__(
        self,
        approved_cidrs: Sequence[str],
        evidence_root: str | os.PathLike,
    ) -> None:
        self._networks = [ipaddress.ip_network(c, strict=False) for c in approved_cidrs]
        self._evidence_root = Path(evidence_root).resolve()

    def check_target(self, addr: str) -> None:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise ScopeViolation(f"invalid address: {addr}") from exc

        for net in self._networks:
            if ip in net:
                return
        raise ScopeViolation(
            f"{addr} is outside all approved VLAN ranges: "
            f"{[str(n) for n in self._networks]}"
        )

    def check_write_path(self, path: str | os.PathLike) -> Path:
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self._evidence_root)
        except ValueError:
            raise ScopeViolation(
                f"write target {resolved} is outside evidence root {self._evidence_root}"
            )
        return resolved

    def approved_ranges(self) -> list[str]:
        return [str(n) for n in self._networks]
