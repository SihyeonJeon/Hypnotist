"""Phase 2 internal test harness — callback listener with scope enforcement.

Every inbound callback is validated against approved VLAN ranges before
any interaction proceeds.  The kill switch can halt the listener at any
time via signal file or explicit engagement.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import yaml

from scope_guard import ScopeGuard, ScopeViolation
from audit_log import AuditLog
from kill_switch import KillSwitch

log = logging.getLogger(__name__)


def load_config(path: str | os.PathLike = "config.yaml") -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


class Harness:
    def __init__(self, config: dict[str, Any]) -> None:
        cidrs = [v["cidr"] for v in config["scope"]["approved_vlans"]]
        evidence_root = config["evidence"]["root"]

        self.scope = ScopeGuard(cidrs, evidence_root)
        self.audit = AuditLog(Path(evidence_root) / "audit.jsonl")
        self.kill = KillSwitch(
            signal_file=config["kill_switch"]["signal_file"],
            check_interval=config["kill_switch"]["check_interval_sec"],
            on_kill=self._on_kill,
        )
        self._server: HTTPServer | None = None
        self._config = config

    def _on_kill(self) -> None:
        log.critical("Shutting down listener — kill switch engaged")
        self.audit.record("kill_switch_engaged", operator="system")
        if self._server:
            threading.Thread(target=self._server.shutdown, daemon=True).start()

    def start(self) -> None:
        cfg = self._config
        bind = cfg["listener"]["bind_addr"]
        port = cfg["listener"]["port"]

        self.kill.start_monitor()
        self.audit.record(
            "harness_start",
            operator=cfg["engagement"]["operator_ids"][0],
            extra={
                "sow": cfg["engagement"]["sow"],
                "phase": cfg["engagement"]["phase"],
                "approved_ranges": self.scope.approved_ranges(),
            },
        )

        handler = _make_handler(self)
        self._server = HTTPServer((bind, port), handler)

        tls_cert = cfg["listener"].get("tls_cert")
        tls_key = cfg["listener"].get("tls_key")
        if tls_cert and tls_key and Path(tls_cert).exists():
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(tls_cert, tls_key)
            self._server.socket = ctx.wrap_socket(
                self._server.socket, server_side=True
            )

        log.info("Listener up on %s:%d", bind, port)
        try:
            self._server.serve_forever()
        finally:
            self.audit.record("harness_stop", operator="system")
            self.audit.close()


def _make_handler(harness: Harness) -> type:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            harness.kill.check_or_raise()

            peer_ip = self.client_address[0]
            try:
                harness.scope.check_target(peer_ip)
            except ScopeViolation as exc:
                harness.audit.record(
                    "scope_violation",
                    operator="system",
                    target=peer_ip,
                    extra={"detail": str(exc)},
                )
                log.warning("SCOPE VIOLATION from %s: %s", peer_ip, exc)
                self.send_error(403, "Target outside approved scope")
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""

            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            harness.audit.record(
                "callback_received",
                operator=harness._config["engagement"]["operator_ids"][0],
                target=peer_ip,
                extra={"path": self.path, "payload_keys": list(payload.keys())},
            )

            response = {"status": "ack", "task": None}
            self._reply(200, response)

        def _reply(self, code: int, data: dict) -> None:
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            log.debug(fmt, *args)

    return CallbackHandler


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = load_config()
    h = Harness(cfg)
    h.start()
