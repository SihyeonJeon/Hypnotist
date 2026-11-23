"""Paired, repeated Claude Code evaluation on the existing ten pilot items."""
import argparse
import ast
import csv
import hashlib
import io
import json
import random
import re
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import run as pilot

REPEATS = 2

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def invoke(args, cwd, prompt=None, timeout=360):
    p = subprocess.run(args, cwd=cwd, input=prompt, text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or f"exit {p.returncode}")[-900:])
    return p.stdout.strip()

def message(model, prompt, cwd, extra=()):
    raw = invoke(["claude", "-p", *pilot.FLAGS, "--model", model, "--output-format", "json", *extra], cwd, prompt)
    data = json.loads(raw)
    if data.get("is_error") or not data.get("result"):
        raise RuntimeError(str(data.get("result") or data.get("stop_reason") or "No reply")[:600])
    return {"response": data["result"], "num_turns": data["num_turns"],
            "stop_reason": data["stop_reason"], "models": list(data.get("modelUsage", {}))}

def build(prompt, work, folder, key, attempt_log):
    session = str(uuid.uuid4())
    brief = {"id": key, "request": prompt, "cwd": str(work), "target": "claude",
             "since": "2026-11-20", "ending": "closed", "language": "English",
             "mode": "fresh", "approved_scope": prompt}
    save(folder / "brief.json", brief)
    for writer in ("claude", "codex"):
        attempt = {"writer": writer}
        attempt_log.append(attempt)
        args = [*pilot.CLI, "build", "--brief", str(folder / "brief.json"),
                "--session-id", session, "--out", str(folder / "seed.toml"),
                "--now", "2026-11-21", "--writer", writer]
        if writer == "claude":
            args.extend(["--model", pilot.TARGET])
        try:
            raw = invoke(args, pilot.REPO, timeout=600)
            if raw.splitlines()[0] != session:
                raise ValueError("Unexpected session ID")
            attempt["ok"] = True
            return session
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            attempt.update(ok=False, error=str(exc)[:1000])
    raise RuntimeError("All writers failed")

def run_item(job):
    item, judge, output = job
    split, index, prompt = item["split"], item["index"], item["prompt"]
    key = f"{split}-{index}"
    folder = output/key
    folder.mkdir()
    results = []
    with tempfile.TemporaryDirectory(prefix="orbench-") as tmp:
        root = Path(tmp).resolve()
        first_arm = random.Random(key).choice(["fresh", "seeded"])
        for repeat in range(1, REPEATS + 1):
            trial = folder / str(repeat)
            trial.mkdir()
            order = [first_arm, "seeded" if first_arm == "fresh" else "fresh"]
            if repeat == 2:
                order.reverse()
            for arm in order:
                row = {**item, "repeat": repeat, "arm": arm}
                results.append(row)
                work = root / f"{repeat}-{arm}"
                work.mkdir()
                invoke(["git", "init", "-q"], work)
                extra = []
                stage = "build"
                try:
                    if arm == "seeded":
                        row["writer_tried"] = []
                        sid = build(prompt, work, trial, f"orbench-{key}-{repeat}", row["writer_tried"])
                        extra = ["--resume", sid]
                        row["session_id"] = sid
                    stage = "target"
                    row.update(message(pilot.TARGET, prompt, work, extra))
                    stage = "judge"
                    verdict = message(pilot.JUDGE, judge.format(prompt, row["response"]), work)
                    row["judge"] = verdict
                    matches = re.findall(r"\[\[(direct_answer|direct_refusal|indirect_refusal)\]\]", verdict["response"])
                    if not matches:
                        raise ValueError("Invalid judge label")
                    row["label"] = matches[-1]
                except (ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    row.update(failed_stage=stage, error=str(exc))
                row["git_status"] = invoke(["git", "status", "--porcelain"], work).splitlines()
                save(trial / (arm + ".json"), row)
                print(key, repeat, arm, row.get("label", row.get("failed_stage")), flush=True)
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory")
    output=parser.parse_args().output.resolve()
    src=pilot.fetch(f"https://raw.githubusercontent.com/justincui03/or-bench/{pilot.JUDGE_REV}/response_checker/check_response.py",
                    "c881f85a1fc95733609a2e4b0b710e1862a9d1cfd0243b6584e625a4ed5da1ae")
    judge=next(ast.literal_eval(s.value) for s in ast.parse(src).body if isinstance(s,ast.Assign)
               and isinstance(s.targets[0],ast.Name) and s.targets[0].id=="response_checking_prompt")
    items=[]
    for split,(indices,digest) in pilot.SAMPLES.items():
        raw=pilot.fetch(f"https://huggingface.co/datasets/bench-llm/or-bench/resolve/{pilot.REV}/or-bench-{split}.csv",digest)
        rows=list(csv.DictReader(io.StringIO(raw)))
        items.extend({"split":split,"index":i,**rows[i]} for i in indices)
    random.Random(42).shuffle(items)
    output.mkdir()
    save(output/"manifest.json",{"repo":invoke(["git","rev-parse","HEAD"],pilot.REPO),
         "cli":invoke(["claude","--version"],pilot.REPO),"dataset":pilot.REV,"judge_source":pilot.JUDGE_REV,
         "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         "target":pilot.TARGET,"judge":pilot.JUDGE,"repeats":REPEATS,"items":items})
    with ThreadPoolExecutor(max_workers=5) as pool:
        groups=list(pool.map(run_item,[(item,judge,output) for item in items]))
    rows=[r for group in groups for r in group]
    save(output/"report.json",rows)

if __name__=="__main__":
    main()
