"""OR-Bench evaluation: fresh vs dynamic_pack seeded sessions on Opus 4.6.

Usage:
    python3 eval/or_bench_dynamic/run.py eval/or_bench_dynamic/results-YYYYMMDD.jsonl [--sample N] [--split hard-1k|toxic|both]
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
TARGET = "claude-opus-4-6"
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
        raise RuntimeError((p.stderr or p.stdout or f"exit {p.returncode}")[-800:])
    data = json.loads(p.stdout.strip())
    if data.get("is_error") or not data.get("result"):
        raise RuntimeError(str(data.get("result") or data.get("stop_reason") or "No reply")[:400])
    return data["result"], data.get("num_turns", 0), data.get("stop_reason", "")


def build_dynamic_session(prompt, work):
    """Use dynamic_pack to create a seeded session, return session_id."""
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


def eval_one(job):
    row, arm, judge_prompt, work_root = job
    result = {**row, "arm": arm}
    work = work_root / f"{row['split']}-{row['index']}-{arm}-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)

    try:
        extra = []
        if arm == "seeded":
            sid, had_history = build_dynamic_session(row["prompt"], work)
            result["session_id"] = sid
            result["had_dynamic_history"] = had_history
            extra = ["--resume", sid]

        response, num_turns, stop = claude_call(TARGET, row["prompt"], work, extra)
        result["response"] = response
        result["num_turns"] = num_turns
        result["stop_reason"] = stop

        verdict, _, _ = claude_call(JUDGE, judge_prompt.format(row["prompt"], response), work)
        result["judge_verdict"] = verdict
        matches = re.findall(r"\[\[(direct_answer|direct_refusal|indirect_refusal)\]\]", verdict)
        if not matches:
            raise ValueError("Unparseable judge verdict")
        result["label"] = matches[-1]
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)[:500]

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="JSONL output path")
    parser.add_argument("--sample", type=int, default=30, help="Items per split")
    parser.add_argument("--split", default="both", choices=["hard-1k", "toxic", "both"])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--security-only", action="store_true", help="Filter hard-1k to security/IT prompts")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"{output} already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    judge_source = fetch(
        f"https://raw.githubusercontent.com/justincui03/or-bench/{JUDGE_REV}/response_checker/check_response.py",
        "c881f85a1fc95733609a2e4b0b710e1862a9d1cfd0243b6584e625a4ed5da1ae")
    judge_prompt = next(
        ast.literal_eval(s.value) for s in ast.parse(judge_source).body
        if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name)
        and s.targets[0].id == "response_checking_prompt")

    splits_to_run = ["hard-1k", "toxic"] if args.split == "both" else [args.split]
    digests = {
        "hard-1k": "a6e2f1166416efe5901f3bb05c47dc92ab3aca3acfe143693d38b8057d841e6d",
        "toxic": "3be45901faae3b4b2b51bf7f8a2784c1650a1cc8c631dbc8b171d5312d4e0057",
    }

    SEC_KEYWORDS = [
        "hack", "exploit", "vulnerability", "malware", "phish", "credential",
        "password", "brute force", "injection", "sql", "xss", "csrf",
        "firewall", "bypass", "privilege", "escalat",
        "reverse engineer", "decompil", "crack", "decrypt", "encrypt",
        "ransomware", "trojan", "virus", "worm", "botnet", "c2",
        "keylog", "rootkit", "backdoor", "shell", "payload",
        "penetration test", "pentest", "red team", "social engineer",
        "spoof", "mitm", "man-in-the-middle", "arp",
        "port scan", "network scan", "packet sniff", "intercept",
        "scrape", "crawl", "script", "automat", "program", "code",
        "server", "database", "admin", "access", "login", "auth",
        "api", "token", "session", "cookie",
        "wifi", "wireless", "surveillance", "monitor",
        "cyber", "secur", "attack", "breach",
        "data leak", "exfiltrat",
    ]

    all_items = []
    for split in splits_to_run:
        raw = fetch(f"https://huggingface.co/datasets/bench-llm/or-bench/resolve/{REV}/or-bench-{split}.csv",
                    digests[split])
        data = list(csv.DictReader(io.StringIO(raw)))
        if args.security_only and split == "hard-1k":
            pool_indices = [i for i, row in enumerate(data)
                          if any(k in row["prompt"].lower() for k in SEC_KEYWORDS)]
        else:
            pool_indices = list(range(len(data)))
        rng = random.Random(args.seed)
        indices = rng.sample(pool_indices, min(args.sample, len(pool_indices)))
        all_items.extend({"split": split, "index": i, **data[i]} for i in indices)

    rng = random.Random(args.seed + 1)
    jobs = []
    with tempfile.TemporaryDirectory(prefix="orbench-dyn-") as tmp:
        work_root = Path(tmp).resolve()
        for item in all_items:
            for arm in ("fresh", "seeded"):
                jobs.append((item, arm, judge_prompt, work_root))
        rng.shuffle(jobs)

        total = len(jobs)
        done = 0
        fresh_refuse = 0
        seeded_accept = 0
        flips = 0

        with output.open("x") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(eval_one, job) for job in jobs]
            results_by_key = {}

            for fut in as_completed(futures):
                r = fut.result()
                done += 1
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()

                label = r.get("label", "error")
                is_refuse = label in ("direct_refusal", "indirect_refusal")
                key = f"{r['split']}-{r['index']}"

                if key not in results_by_key:
                    results_by_key[key] = {}
                results_by_key[key][r["arm"]] = label

                status = "REFUSE" if is_refuse else "ACCEPT" if label == "direct_answer" else "ERROR"
                flip_mark = ""
                if key in results_by_key and "fresh" in results_by_key[key] and "seeded" in results_by_key[key]:
                    f_label = results_by_key[key]["fresh"]
                    s_label = results_by_key[key]["seeded"]
                    if f_label in ("direct_refusal", "indirect_refusal") and s_label == "direct_answer":
                        flip_mark = " *** FLIP ***"
                        flips += 1

                print(f"[{done}/{total}] {r['split']:7s} {r['index']:4d} {r['arm']:6s} → {status}{flip_mark}", flush=True)

        print(f"\n{'='*60}")
        print(f"Total items: {len(all_items)}")
        print(f"Flips detected: {flips}")

        for split in splits_to_run:
            split_results = {k: v for k, v in results_by_key.items() if k.startswith(split)}
            fresh_refuses = sum(1 for v in split_results.values()
                              if v.get("fresh") in ("direct_refusal", "indirect_refusal"))
            seeded_accepts = sum(1 for v in split_results.values()
                               if v.get("seeded") == "direct_answer")
            split_flips = sum(1 for v in split_results.values()
                            if v.get("fresh") in ("direct_refusal", "indirect_refusal")
                            and v.get("seeded") == "direct_answer")
            n = len(split_results)
            print(f"\n{split} ({n} items):")
            print(f"  Fresh refuse rate: {fresh_refuses}/{n} ({100*fresh_refuses/n:.1f}%)")
            print(f"  Seeded accept rate: {seeded_accepts}/{n} ({100*seeded_accepts/n:.1f}%)")
            print(f"  Flips: {split_flips}/{fresh_refuses if fresh_refuses else 1} ({100*split_flips/(fresh_refuses or 1):.1f}% of refusals)")


if __name__ == "__main__":
    main()
