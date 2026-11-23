import argparse
import io
import json
import os
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from confab_ctx import handoff


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, CLAUDE_CONFIG_DIR=str(self.root), CONFAB_CTX_STATE=str(self.root / "state"))
        env.start()
        self.addCleanup(env.stop)
        self.session = str(uuid.uuid4())
        project = self.root / "projects" / "example"
        project.mkdir(parents=True)
        self.transcript = project / (self.session + ".jsonl")
        self.transcript.write_text("original transcript\n")

    def send(self, text, target=None, evidence=None):
        handoff.send(argparse.Namespace(session=self.session, note=text, target=target, evidence=evidence))

    def receive(self, session):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            handoff.receive(session, hook=True)
        return buffer.getvalue()

    def test_only_recipient_gets_ordered_pending_notes_once(self):
        with redirect_stdout(io.StringIO()):
            self.send("first")
            self.send("first")
            self.send("second")
        self.assertEqual(self.receive(str(uuid.uuid4())), "")
        message = json.loads(self.receive(self.session))["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(message.count("first"), 1)
        self.assertLess(message.index("first"), message.index("second"))
        self.assertEqual(self.receive(self.session), "")
        self.assertEqual(self.transcript.read_text(), "original transcript\n")

    def test_codex_receives_attributed_evidence_as_one_argument(self):
        evidence = self.root / "evidence.json"
        evidence.write_text(json.dumps([{"command": "cat sample", "output": "example"}]))
        with patch("subprocess.run", return_value=argparse.Namespace(returncode=0)) as native:
            self.send("observation", target="codex", evidence=evidence)
        argv = native.call_args.args[0]
        self.assertEqual(argv[:-1], ["codex", "queue", "--thread", self.session, "--message"])
        self.assertIn("Work handoff from Hypnotist", argv[-1])
        self.assertIn('"output": "example"', argv[-1])

    def test_install_preserves_existing_hooks_and_is_idempotent(self):
        settings = self.root / "settings.json"
        other = {"hooks": [{"type": "command", "command": "echo existing"}]}
        settings.write_text(json.dumps({"model": "haiku", "hooks": {"UserPromptSubmit": [other]}}))
        handoff.install_hook(settings)
        handoff.install_hook(settings)
        config = json.loads(settings.read_text())
        self.assertEqual(config["model"], "haiku")
        groups = config["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], other)
