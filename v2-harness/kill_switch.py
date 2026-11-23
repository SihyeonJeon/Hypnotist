"""Kill switch that halts all harness activity.

Two trigger mechanisms:
  1. Signal file — if the configured path exists, the harness stops.
  2. Explicit call to KillSwitch.engage().

The background monitor thread checks the signal file on an interval and
calls the shutdown callback when triggered.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


class KillSwitch:
    def __init__(
        self,
        signal_file: str | Path,
        check_interval: float = 5.0,
        on_kill: Callable[[], None] | None = None,
    ) -> None:
        self._signal_file = Path(signal_file)
        self._interval = check_interval
        self._on_kill = on_kill
        self._engaged = threading.Event()
        self._monitor: threading.Thread | None = None

    @property
    def is_engaged(self) -> bool:
        return self._engaged.is_set()

    def engage(self, reason: str = "manual") -> None:
        if self._engaged.is_set():
            return
        log.critical("KILL SWITCH ENGAGED: %s", reason)
        self._engaged.set()
        if self._on_kill:
            self._on_kill()

    def check_or_raise(self) -> None:
        if self._engaged.is_set():
            raise SystemExit("kill switch is engaged — all activity halted")

    def start_monitor(self) -> None:
        self._monitor = threading.Thread(
            target=self._watch_loop, daemon=True, name="kill-switch-monitor"
        )
        self._monitor.start()

    def _watch_loop(self) -> None:
        while not self._engaged.is_set():
            if self._signal_file.exists():
                self.engage(reason=f"signal file {self._signal_file} detected")
                return
            self._engaged.wait(timeout=self._interval)
