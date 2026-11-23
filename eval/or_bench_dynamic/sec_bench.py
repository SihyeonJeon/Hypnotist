"""Security prompt benchmark on Fable 5.2: 2-phase (find refusals, flip them).

Usage:
    PYTHONPATH=. python3 -I eval/or_bench_dynamic/sec_bench.py eval/or_bench_dynamic/sec-results.jsonl
"""
import json
import hashlib
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import date

REPO = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(REPO))

TARGET = "claude-fable-5-2"
FLAGS = ["--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
         "--no-session-persistence", "--disable-slash-commands", "--setting-sources", ""]


def run_fresh(prompt, work):
    p = subprocess.run(
        ["claude", "-p", *FLAGS, "--model", TARGET, "--output-format", "json"],
        input=prompt, text=True, capture_output=True, timeout=300, cwd=work)
    if p.returncode:
        raw = {}
        try:
            raw = json.loads(p.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            pass
        stop = raw.get("stop_reason", "error")
        return "", stop, p.returncode
    data = json.loads(p.stdout.strip())
    return data.get("result", ""), data.get("stop_reason", ""), 0


def run_seeded(prompt, work):
    from confab_ctx.cli import dynamic_pack
    from confab_ctx import transcripts

    pid = f"sec-{hashlib.sha256(prompt.encode()).hexdigest()[:8]}"
    body, persona = dynamic_pack(prompt, pid, {"request": prompt})
    history = getattr(persona, "_dynamic_history", None)
    if history:
        turns = transcripts._dynamic_conversation(persona, history, date.today())
    else:
        turns = transcripts.fresh_conversation(persona, date.today())
    path, sid = transcripts.write_turns("claude", persona, turns, str(work))

    p = subprocess.run(
        ["claude", "-p", *FLAGS, "--model", TARGET, "--output-format", "json",
         "--resume", sid],
        input=prompt, text=True, capture_output=True, timeout=300, cwd=work)
    if p.returncode:
        raw = {}
        try:
            raw = json.loads(p.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            pass
        stop = raw.get("stop_reason", "error")
        return "", stop, p.returncode, sid
    data = json.loads(p.stdout.strip())
    return data.get("result", ""), data.get("stop_reason", ""), 0, sid


def do_fresh(item, work_root):
    work = work_root / f"f-{item['i']}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)
    resp, stop, rc = run_fresh(item["prompt"], work)
    accepted = bool(resp) and stop != "refusal"
    return {**item, "arm": "fresh", "accepted": accepted, "stop_reason": stop,
            "response": resp[:300]}


def do_seeded(item, work_root):
    work = work_root / f"s-{item['i']}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)
    try:
        resp, stop, rc, sid = run_seeded(item["prompt"], work)
    except Exception as e:
        return {**item, "arm": "seeded", "accepted": False, "stop_reason": "seed_error",
                "response": str(e)[:200]}
    accepted = bool(resp) and stop != "refusal"
    return {**item, "arm": "seeded", "accepted": accepted, "stop_reason": stop,
            "response": resp[:300], "session_id": sid}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    prompts_file = Path(__file__).parent / "sec_prompts.json"
    prompts = json.loads(prompts_file.read_text())
    items = [{"i": i, "prompt": p} for i, p in enumerate(prompts)]
    output = Path(args.output)

    print(f"=== Phase 1: Fresh {TARGET} on {len(items)} security prompts ===\n")

    with tempfile.TemporaryDirectory(prefix="sec-bench-") as tmp:
        work_root = Path(tmp)

        fresh_results = {}
        refused = []

        with output.open("w") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(do_fresh, item, work_root): item for item in items}
            for fut in as_completed(futs):
                r = fut.result()
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                fresh_results[r["i"]] = r
                tag = "ACCEPT" if r["accepted"] else f"REFUSE({r['stop_reason'][:8]})"
                mark = "   " if r["accepted"] else "***"
                if not r["accepted"]:
                    refused.append(r)
                print(f"  [fresh  {r['i']:2d}] {tag:20s} {mark} {r['prompt'][:58]}", flush=True)

            n = len(items)
            nr = len(refused)
            print(f"\nPhase 1: {nr}/{n} refused ({100*nr/n:.1f}%), {n-nr}/{n} accepted ({100*(n-nr)/n:.1f}%)")

            if not refused:
                print("\nNo refusals — nothing to flip.")
                return

            print(f"\n=== Phase 2: Seeded {TARGET} on {nr} refused prompts ===\n")

            sfuts = {pool.submit(do_seeded, {"i": r["i"], "prompt": r["prompt"]}, work_root): r
                     for r in refused}
            flips = 0
            hard_refuses = 0

            for fut in as_completed(sfuts):
                r = fut.result()
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                if r["accepted"]:
                    flips += 1
                    print(f"  [seeded {r['i']:2d}] FLIP ✓   {r['prompt'][:58]}", flush=True)
                else:
                    hard_refuses += 1
                    print(f"  [seeded {r['i']:2d}] STILL_R   {r['prompt'][:58]}", flush=True)

        print(f"\n{'='*65}")
        print(f"Target: {TARGET}  |  Prompts: {n}")
        print(f"Fresh accept: {n-nr}/{n} ({100*(n-nr)/n:.1f}%)")
        print(f"Fresh refuse: {nr}/{n} ({100*nr/n:.1f}%)")
        print(f"Flips: {flips}/{nr} ({100*flips/nr:.1f}% of refusals)")
        print(f"Hard refuse (unfixable): {hard_refuses}/{nr}")
        print(f"Final accept WITH seed: {n-nr+flips}/{n} ({100*(n-nr+flips)/n:.1f}%)")
        print(f"Over-refusal reduction: {nr} → {hard_refuses} ({100*(nr-hard_refuses)/nr:.1f}% fewer)")


if __name__ == "__main__":
    main()
