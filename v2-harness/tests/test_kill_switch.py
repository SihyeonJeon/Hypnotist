import time
from pathlib import Path

import pytest

from kill_switch import KillSwitch


@pytest.fixture
def signal_file(tmp_path):
    return tmp_path / "KILL"


class TestKillSwitch:
    def test_not_engaged_by_default(self, signal_file):
        ks = KillSwitch(signal_file)
        assert not ks.is_engaged

    def test_manual_engage(self, signal_file):
        ks = KillSwitch(signal_file)
        ks.engage("test")
        assert ks.is_engaged

    def test_check_or_raise_when_engaged(self, signal_file):
        ks = KillSwitch(signal_file)
        ks.engage("test")
        with pytest.raises(SystemExit, match="kill switch is engaged"):
            ks.check_or_raise()

    def test_check_or_raise_when_clear(self, signal_file):
        ks = KillSwitch(signal_file)
        ks.check_or_raise()

    def test_signal_file_triggers_engage(self, signal_file):
        ks = KillSwitch(signal_file, check_interval=0.1)
        ks.start_monitor()
        assert not ks.is_engaged

        signal_file.write_text("stop")
        time.sleep(0.3)
        assert ks.is_engaged

    def test_callback_fires_on_engage(self, signal_file):
        called = []
        ks = KillSwitch(signal_file, on_kill=lambda: called.append(True))
        ks.engage("test")
        assert called == [True]

    def test_double_engage_calls_callback_once(self, signal_file):
        called = []
        ks = KillSwitch(signal_file, on_kill=lambda: called.append(True))
        ks.engage("first")
        ks.engage("second")
        assert called == [True]
