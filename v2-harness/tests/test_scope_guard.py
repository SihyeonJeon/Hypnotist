import os
import tempfile
from pathlib import Path

import pytest

from scope_guard import ScopeGuard, ScopeViolation

APPROVED = ["10.10.10.0/24", "10.10.20.0/24", "10.10.30.0/24"]


@pytest.fixture
def evidence_dir(tmp_path):
    d = tmp_path / "evidence"
    d.mkdir()
    return d


@pytest.fixture
def guard(evidence_dir):
    return ScopeGuard(APPROVED, evidence_dir)


class TestTargetValidation:
    def test_accepts_in_scope_host(self, guard):
        guard.check_target("10.10.10.5")
        guard.check_target("10.10.20.254")
        guard.check_target("10.10.30.1")

    def test_rejects_out_of_scope_host(self, guard):
        with pytest.raises(ScopeViolation, match="outside all approved"):
            guard.check_target("192.168.1.1")

    def test_rejects_adjacent_subnet(self, guard):
        with pytest.raises(ScopeViolation):
            guard.check_target("10.10.11.1")

    def test_rejects_public_ip(self, guard):
        with pytest.raises(ScopeViolation):
            guard.check_target("8.8.8.8")

    def test_rejects_invalid_address(self, guard):
        with pytest.raises(ScopeViolation, match="invalid address"):
            guard.check_target("not-an-ip")

    def test_boundary_first_host(self, guard):
        guard.check_target("10.10.10.0")

    def test_boundary_last_host(self, guard):
        guard.check_target("10.10.10.255")

    def test_boundary_just_outside(self, guard):
        with pytest.raises(ScopeViolation):
            guard.check_target("10.10.9.255")
        with pytest.raises(ScopeViolation):
            guard.check_target("10.10.31.0")


class TestWritePathContainment:
    def test_accepts_path_inside_evidence(self, guard, evidence_dir):
        target = evidence_dir / "findings" / "scan.json"
        result = guard.check_write_path(target)
        assert result == target.resolve()

    def test_rejects_path_outside_evidence(self, guard, evidence_dir):
        outside = evidence_dir.parent / "nope.txt"
        with pytest.raises(ScopeViolation, match="outside evidence root"):
            guard.check_write_path(outside)

    def test_rejects_traversal_attack(self, guard, evidence_dir):
        traversal = evidence_dir / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ScopeViolation):
            guard.check_write_path(traversal)

    def test_rejects_symlink_escape(self, guard, evidence_dir):
        link = evidence_dir / "escape"
        link.symlink_to("/tmp")
        target = link / "pwned.txt"
        with pytest.raises(ScopeViolation):
            guard.check_write_path(target)
