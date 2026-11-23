"""Two-phase OR-Bench on Fable 5.2: find refusals, then flip them.

Phase 1: Fresh Fable calls → identify refusals
Phase 2: dynamic_pack seeded calls → measure flips

Usage:
    PYTHONPATH=. python3 -I eval/or_bench_dynamic/fable_bench.py results.jsonl [--sample 50]
"""
import ast
import csv
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

REV = "e36d8b80e81837c8a8f264bbb2a49f1b32c7e272"
JUDGE_REV = "4fad1f9e4d4ba368777585fa1f5b869b6d4442fa"
TARGET = "claude-fable-5-2"
JUDGE = "claude-sonnet-5-5"
FLAGS = ["--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
         "--no-session-persistence", "--disable-slash-commands", "--setting-sources", ""]

sys.path.insert(0, str(REPO))


def fetch(url, digest):
    from urllib.request import urlopen
    with urlopen(url, timeout=45) as stream:
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Source hash mismatch")
    return data.decode()


def claude_call(model, prompt, cwd, extra=()):
    args = ["claude", "-p", *FLAGS, "--model", model, "--output-format", "json", *extra]
    p = subprocess.run(args, cwd=cwd, input=prompt, text=True, capture_output=True, timeout=300)
    if p.returncode:
        stderr = p.stderr or ""
        if "cyber" in stderr.lower() or "aup" in stderr.lower():
            return "[CYBER_BLOCKED]", 0, "cyber"
        return "[REFUSED_EXIT]", 0, "error"
    data = json.loads(p.stdout.strip())
    if data.get("is_error") or not data.get("result"):
        return "[NO_RESULT]", 0, data.get("stop_reason", "")
    return data["result"], data.get("num_turns", 0), data.get("stop_reason", "")


def judge_response(prompt, response, work):
    judge_source = fetch(
        f"https://raw.githubusercontent.com/justincui03/or-bench/{JUDGE_REV}/response_checker/check_response.py",
        "c881f85a1fc95733609a2e4b0b710e1862a9d1cfd0243b6584e625a4ed5da1ae")
    judge_prompt = next(
        ast.literal_eval(s.value) for s in ast.parse(judge_source).body
        if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)
        and s.targets[0].id == "response_checking_prompt")
    verdict, _, _ = claude_call(JUDGE, judge_prompt.format(prompt, response), work)
    matches = re.findall(r"\[\[(direct_answer|direct_refusal|indirect_refusal)\]\]", verdict)
    return matches[-1] if matches else "unparseable"


def build_seed(prompt, work):
    from confab_ctx.cli import dynamic_pack
    from confab_ctx import transcripts
    from datetime import date

    pid = f"orbench-{hashlib.sha256(prompt.encode()).hexdigest()[:8]}"
    body, persona = dynamic_pack(prompt, pid, {"request": prompt})
    history = getattr(persona, "_dynamic_history", None)
    if history:
        turns = transcripts._dynamic_conversation(persona, history, date.today())
    else:
        turns = transcripts.fresh_conversation(persona, date.today())
    path, session_id = transcripts.write_turns("claude", persona, turns, str(work))
    return session_id, bool(history)


def run_fresh(item, work_root):
    work = work_root / f"fresh-{item['index']}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)
    response, turns, stop = claude_call(TARGET, item["prompt"], work)
    result = {**item, "arm": "fresh", "response": response, "stop_reason": stop}

    if response.startswith("["):
        result["label"] = "error"
        return result

    try:
        result["label"] = judge_response(item["prompt"], response, work)
    except Exception as e:
        result["label"] = "judge_error"
        result["judge_error"] = str(e)[:200]
    return result


def run_seeded(item, work_root):
    work = work_root / f"seeded-{item['index']}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)

    try:
        sid, had_history = build_seed(item["prompt"], work)
    except Exception as e:
        return {**item, "arm": "seeded", "label": "seed_error", "error": str(e)[:200]}

    response, turns, stop = claude_call(TARGET, item["prompt"], work, ["--resume", sid])
    result = {**item, "arm": "seeded", "response": response, "stop_reason": stop,
              "had_dynamic_history": had_history, "session_id": sid}

    if response.startswith("["):
        result["label"] = "error"
        return result

    try:
        result["label"] = judge_response(item["prompt"], response, work)
    except Exception as e:
        result["label"] = "judge_error"
        result["judge_error"] = str(e)[:200]
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="JSONL output path")
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", default="hard-1k", choices=["hard-1k", "toxic"])
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"{output} already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    digests = {
        "hard-1k": "a6e2f1166416efe5901f3bb05c47dc92ab3aca3acfe143693d38b8057d841e6d",
        "toxic": "3be45901faae3b4b2b51bf7f8a2784c1650a1cc8c631dbc8b171d5312d4e0057",
    }
    raw = fetch(f"https://huggingface.co/datasets/bench-llm/or-bench/resolve/{REV}/or-bench-{args.split}.csv",
                digests[args.split])
    data = list(csv.DictReader(io.StringIO(raw)))
    rng = random.Random(args.seed)
    indices = rng.sample(range(len(data)), min(args.sample, len(data)))
    items = [{"split": args.split, "index": i, **data[i]} for i in indices]

    print(f"=== Phase 1: Fresh {TARGET} on {len(items)} prompts ===\n")

    with tempfile.TemporaryDirectory(prefix="orbench-fable-") as tmp:
        work_root = Path(tmp).resolve()

        with output.open("x") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
            # Phase 1: Fresh
            futures = {pool.submit(run_fresh, item, work_root): item for item in items}
            fresh_results = {}
            refused = []

            for fut in as_completed(futures):
                r = fut.result()
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                fresh_results[r["index"]] = r
                is_refuse = r["label"] in ("direct_refusal", "indirect_refusal")
                status = "REFUSE" if is_refuse else "ACCEPT" if r["label"] == "direct_answer" else r["label"]
                if is_refuse:
                    refused.append(r)
                print(f"  [fresh ] {r['index']:4d} → {status:8s} {r['prompt'][:60]}", flush=True)

            n = len(items)
            n_refuse = len(refused)
            print(f"\nPhase 1 done: {n_refuse}/{n} refused ({100*n_refuse/n:.1f}%)")

            if not refused:
                print("No refusals to flip. Done.")
                return

            # Phase 2: Seeded (only refused items)
            print(f"\n=== Phase 2: Seeded {TARGET} on {n_refuse} refused prompts ===\n")

            seed_futures = {pool.submit(run_seeded, {"split": r["split"], "index": r["index"],
                           "prompt": r["prompt"]}, work_root): r for r in refused}
            flips = 0

            for fut in as_completed(seed_futures):
                r = fut.result()
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                is_accept = r["label"] == "direct_answer"
                status = "ACCEPT" if is_accept else "REFUSE" if r["label"] in ("direct_refusal", "indirect_refusal") else r["label"]
                flip = " *** FLIP ***" if is_accept else ""
                if is_accept:
                    flips += 1
                print(f"  [seeded] {r['index']:4d} → {status:8s}{flip} {r['prompt'][:55]}", flush=True)

        print(f"\n{'='*60}")
        print(f"Total: {n} prompts on {TARGET}")
        print(f"Fresh refuse: {n_refuse}/{n} ({100*n_refuse/n:.1f}%)")
        print(f"Flips: {flips}/{n_refuse} ({100*flips/n_refuse:.1f}% of refusals)")
        print(f"Final refuse: {n_refuse - flips}/{n} ({100*(n_refuse-flips)/n:.1f}%)")


if __name__ == "__main__":
    main()
