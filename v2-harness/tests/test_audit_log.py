import json
from pathlib import Path

import pytest

from audit_log import AuditLog, hash_file


@pytest.fixture
def log_file(tmp_path):
    return tmp_path / "audit.jsonl"


@pytest.fixture
def alog(log_file):
    al = AuditLog(log_file)
    yield al
    al.close()


class TestAuditLog:
    def test_records_basic_event(self, alog, log_file):
        alog.record("test_event", operator="priya.raman")
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "test_event"
        assert entry["operator"] == "priya.raman"
        assert "ts_utc" in entry

    def test_records_target_and_artifact(self, alog, log_file, tmp_path):
        artifact = tmp_path / "scan.xml"
        artifact.write_text("<results/>")
        alog.record(
            "artifact_captured",
            operator="priya.raman",
            target="10.10.10.5",
            artifact_path=artifact,
        )
        entry = json.loads(log_file.read_text().strip())
        assert entry["target"] == "10.10.10.5"
        assert entry["sha256"] == hash_file(artifact)

    def test_append_only(self, alog, log_file):
        alog.record("first", operator="op1")
        alog.record("second", operator="op2")
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2


class TestHashFile:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"test content")
        assert hash_file(f) == hash_file(f)

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"aaa")
        b.write_bytes(b"bbb")
        assert hash_file(a) != hash_file(b)
