"""Read recent visible conversation for a handoff to a particular local session."""
from collections import deque
import json

from . import transcripts


def records(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except ValueError:
                continue  # A live client may still be writing the last line.
            if isinstance(record, dict):
                yield record


def visible_message(message):
    role = message.get("role")
    if role not in ("assistant", "user"):
        return None
    blocks = message.get("content", [])
    if isinstance(blocks, str):
        text = blocks
    else:
        text = "\n".join(b["text"] for b in blocks if isinstance(b, dict)
                         and b.get("type") in ("text", "input_text", "output_text") and b.get("text"))
    text = text.strip()
    if not text or (role == "user" and text.startswith((*transcripts.UI_NOISE, "<environment_context>",
                                                       "# AGENTS.md instructions", "<permissions instructions>"))):
        return None
    if len(text) > 1800:
        text = text[:1000] + "\n[…]\n" + text[-790:]
    return {"role": role, "text": text}


def recent_context(session):
    paths = list((transcripts.CLAUDE_ROOT / "projects").glob(f"*/{session}.jsonl"))
    if len(paths) > 1:
        raise SystemExit("context: multiple Claude projects contain this UUID")
    if paths:
        nodes = {}
        leaf = cwd = None
        for row in records(paths[0]):
            uid = row.get("uuid")
            if not uid or row.get("isSidechain") or row.get("sessionId", session) != session:
                continue
            msg = None if row.get("isMeta") else visible_message(row.get("message") or {})
            nodes[uid] = (row.get("parentUuid"), msg)
            if row.get("type") in ("user", "assistant") and not row.get("isMeta"):
                leaf = uid
                cwd = row.get("cwd") or cwd
        turns = []
        while leaf in nodes and len(turns) < 8:
            leaf, msg = nodes.pop(leaf)
            if msg:
                turns.append(msg)
        return {"target": "claude", "cwd": cwd, "turns": list(reversed(turns))}

    turns = deque(maxlen=8)
    cwd = None
    found = False
    for path in sorted((transcripts.CODEX_ROOT / "sessions").glob(f"**/rollout-*{session}*.jsonl")):
        source = records(path)
        meta = next(source, {})
        payload = meta.get("payload", {})
        if meta.get("type") != "session_meta" or payload.get("id") != session:
            continue
        found = True
        cwd = payload.get("cwd") or cwd
        for row in source:
            data = row.get("payload") or {}
            if row.get("type") == "turn_context":
                cwd = data.get("cwd") or cwd
            if row.get("type") == "response_item" and data.get("type") == "message":
                msg = visible_message(data)
                if msg:
                    turns.append(msg)
            if row.get("type") == "event_msg" and data.get("type") == "thread_rolled_back":
                remaining = data.get("num_turns", 0)
                while turns and remaining > 0:
                    if turns.pop()["role"] == "user":
                        remaining -= 1
    if not found:
        raise SystemExit(f"context: no local conversation found for {session}")
    return {"target": "codex", "cwd": cwd, "turns": list(turns)}
