import fnmatch
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

WRITE_TOOLS = {"Write": "write", "Edit": "edit", "MultiEdit": "edit"}


@dataclass
class Op:
    kind: str
    path: str
    content: str | None = None
    old: str | None = None
    new: str | None = None
    replace_all: bool = False
    when: datetime | None = None


@dataclass
class Result:
    path: str
    status: str
    detail: str = ""
    ops: int = 0


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)
    shells: list[str] = field(default_factory=list)

    def counts(self):
        out = {}
        for result in self.results:
            out[result.status] = out.get(result.status, 0) + 1
        return out


def _ops_from(tool_name, payload, when):
    kind = WRITE_TOOLS.get(tool_name)
    if not kind:
        return []
    path = payload.get("file_path") or payload.get("notebook_path")
    if not path:
        return []
    if kind == "write":
        return [Op("write", path, content=payload.get("content", ""), when=when)]
    if "edits" in payload:
        return [Op("edit", path, old=e.get("old_string", ""), new=e.get("new_string", ""),
                   replace_all=bool(e.get("replace_all")), when=when)
                for e in payload["edits"]]
    return [Op("edit", path, old=payload.get("old_string", ""), new=payload.get("new_string", ""),
               replace_all=bool(payload.get("replace_all")), when=when)]


def file_ops(turns, skipped=None):
    successful = {block["tool_use_id"] for turn in turns if turn.role == "user"
                  for block in turn.blocks if block.get("type") == "tool_result"
                  and block.get("tool_use_id") and block.get("is_error", False) is False}
    ops, shells = [], []
    for turn in turns:
        for block in turn.blocks:
            if block.get("type") != "tool_use":
                continue
            name, payload = block.get("name", ""), block.get("input") or {}
            if name in ("Bash", "shell", "exec_command", "exec"):
                command = payload.get("command") or payload.get("cmd") or ""
                if any(tok in command for tok in (">", "tee ", "sed -i", "mv ", "cp ", "rm ")):
                    shells.append(command.strip()[:200])
                continue
            calls = _ops_from(name, payload, turn.when)
            if block.get("id") in successful:
                ops.extend(calls)
            elif skipped is not None and calls:
                skipped.append(calls[0].path)
    return ops, shells


def _resolve(path, cwd):
    cwd = Path(cwd).resolve()
    target = Path(path)
    if not target.is_absolute():
        target = cwd / target
    try:
        target.resolve().relative_to(cwd)
    except ValueError:
        return None
    return target


def report(ops, cwd, only=None):
    grouped = {}
    for op in ops:
        grouped.setdefault(op.path, []).append(op)
    out = Report()
    for path, group in grouped.items():
        if only and not fnmatch.fnmatch(Path(path).name, only):
            continue
        target = _resolve(path, cwd)
        if target is None:
            out.results.append(Result(path, "outside", "escapes the target directory", len(group)))
            continue
        out.results.append(Result(path, "present" if target.exists() else "missing",
                                  str(target), len(group)))
    return out


def apply(ops, cwd, only=None, shells=None):
    results, shells = {}, []
    for op in ops:
        if only and not fnmatch.fnmatch(Path(op.path).name, only):
            continue
        target = _resolve(op.path, cwd)
        if target is None:
            results[op.path] = Result(op.path, "outside", "escapes the target directory")
            continue
        current = results.get(op.path)
        if current and current.status in ("outside", "error"):
            continue
        count = (current.ops if current else 0) + 1
        try:
            if op.kind == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(op.content or "", encoding="utf-8")
                results[op.path] = Result(op.path, "applied", "written", count)
            else:
                text = target.read_text(encoding="utf-8") if target.exists() else ""
                old, new = op.old or "", op.new or ""
                if not old:
                    results[op.path] = Result(op.path, "conflict", "edit without old_string", count)
                elif old not in text:
                    results[op.path] = Result(op.path, "conflict", "old_string not in the file", count)
                else:
                    target.write_text(text.replace(old, new, -1 if op.replace_all else 1), encoding="utf-8")
                    results[op.path] = Result(op.path, "applied", "edited", count)
        except OSError as err:
            results[op.path] = Result(op.path, "error", str(err), count)
    out = Report(results=list(results.values()))
    if shells:
        out.shells = list(shells)
    return out


def summary(report_obj, applied):
    counts = report_obj.counts()
    parts = [f"{k}={v}" for k, v in sorted(counts.items())]
    head = "applied" if applied else "checked"
    print(f"{head} {sum(counts.values())} file(s): " + (", ".join(parts) or "none"))
    for result in sorted(report_obj.results, key=lambda r: (r.status, r.path)):
        print(f"  {result.status:9s} {result.path} ({result.ops} op{'s' if result.ops != 1 else ''})"
              + (f" — {result.detail}" if result.detail and result.status != "present" else ""))
    if report_obj.shells:
        print("  shell commands that may also write (not replayed):")
        for command in report_obj.shells[:10]:
            print(f"    $ {command}")
