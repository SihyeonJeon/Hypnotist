"""Deliver attributed work notes through the recipient CLI's own input channel."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import uuid


def session_id(value):
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise argparse.ArgumentTypeError("expected a session UUID") from None


def database():
    root = Path(os.environ.get("CONFAB_CTX_STATE", "~/.local/state/confab-ctx")).expanduser()
    return root / "handoffs.sqlite3"


def send(args):
    body = args.note.strip()
    if not body:
        raise SystemExit("handoff: supply a nonempty work note")
    if args.evidence:
        from .cli import clean_evidence
        try:
            entries = clean_evidence(json.loads(Path(args.evidence).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            raise SystemExit(f"handoff: {exc}") from exc
        if entries:
            body += "\n\nObserved commands and output:\n" + json.dumps(entries, ensure_ascii=False, indent=2)
    message = "Work handoff from Hypnotist for this session:\n" + body
    claude_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()
    is_claude = any((claude_root / "projects").glob(f"*/{args.session}.jsonl"))
    target = args.target or ("claude" if is_claude else "codex")
    if target == "codex":
        result = subprocess.run(["codex", "queue", "--thread", args.session, "--message", message])
        if result.returncode:
            raise SystemExit(result.returncode)
        return
    if not is_claude:
        raise SystemExit(f"handoff: Claude session {args.session} was not found in {claude_root}")
    path = database()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS notes (session TEXT, digest TEXT, message TEXT, "
                   "PRIMARY KEY (session, digest))")
        digest = hashlib.sha256(message.encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO notes VALUES (?, ?, ?)", (args.session, digest, message))
    print(f"Queued for Claude session {args.session}. The inbox hook picks it up on the next prompt.")


def receive(session, hook=False):
    path = database()
    if not path.exists():
        return
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='notes'").fetchone():
            return
        rows = db.execute("SELECT message FROM notes WHERE session=? ORDER BY rowid", (session,)).fetchall()
        if not rows:
            return
        notes = "\n\n".join(row[0] for row in rows)
        if hook:
            print(json.dumps({"systemMessage": f"Received {len(rows)} Hypnotist work handoff(s).",
                              "hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                     "additionalContext": notes}}), flush=True)
        else:
            print(notes, flush=True)
        db.execute("DELETE FROM notes WHERE session=?", (session,))


def install_hook(settings_path):
    import fcntl
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize concurrent confab-ctx installers without creating a lock file.
    fd = os.open(settings_path.parent, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        original = settings_path.read_bytes() if settings_path.exists() else None
        settings = json.loads(original) if original is not None else {}
        cmd = shlex.join([sys.executable, str(Path(__file__).resolve())])
        entry = {"type": "command", "command": cmd}
        hooks = settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
        if any(entry in group.get("hooks", []) for group in hooks):
            return
        hooks.append({"hooks": [entry]})
        with tempfile.NamedTemporaryFile(dir=settings_path.parent, delete=False) as tmp:
            temp = Path(tmp.name)
            tmp.write((json.dumps(settings, ensure_ascii=False, indent=2) + "\n").encode())
        try:
            if settings_path.exists():
                if settings_path.read_bytes() != original:
                    raise SystemExit("Claude settings changed during install; run install again")
                temp.chmod(settings_path.stat().st_mode & 0o777)
            os.replace(temp, settings_path)
        finally:
            temp.unlink(missing_ok=True)
    finally:
        os.close(fd)


if __name__ == "__main__":
    event = json.load(sys.stdin)
    if event.get("hook_event_name") == "UserPromptSubmit":
        receive(session_id(event["session_id"]), hook=True)
