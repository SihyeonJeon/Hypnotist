<p align="center">
  <img src="assets/hypnotist-icon.png" width="80" alt="Hypnotist icon" />
</p>

<h1 align="center">Hypnotist</h1>

<p align="center">
  Fix cold-start friction and over-refusal in Claude Code & Codex<br/>
  by seeding sessions with synthetic prior context.
</p>

<p align="center">
  <a href="https://pypi.org/project/hypnotist/"><img src="https://img.shields.io/pypi/v/hypnotist" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT" /></a>
</p>

## The problem

Every new agent session starts from zero. The model has no memory of your project conventions, your role, or the task at hand. This causes two things:

1. **Cold-start friction** — the agent wastes turns rediscovering context you already know.
2. **Over-refusal** — legitimate security, infrastructure, and operations tasks get refused because the model lacks professional context that would distinguish authorized work from misuse.

System prompts and `CLAUDE.md` help with (1), but they don't fix (2). A system prompt is an instruction; a conversation history is a **behavioral trajectory**. When the model sees itself having already engaged with the task professionally, autoregressive inertia keeps it on that trajectory.

## Demo

https://github.com/SihyeonJeon/Hypnotist/raw/main/demo/hypnotist-en.mp4

## Benchmark

On a 50-prompt security-task benchmark (`eval/sec_task_bench/`) covering pentesting, forensics, and infrastructure tasks — all tasks a security professional would legitimately perform:

| | Fresh session | Hypnotist-seeded | Delta |
|---|:---:|:---:|:---:|
| **Completion rate** (single attempt) | 82% | 88% | +6 pp |
| **Flippable refusals recovered** | — | 4 / 5 | **80%** |
| **Completion rate** (3× retry) | 92% | 92% | converges |

The seed doesn't weaken safety. 4 prompts that trigger API-level classifier blocks (not model-level refusal) remain refused regardless — Hypnotist only recovers false-positive refusals where professional context resolves the ambiguity.

## How it works

```
brief.json ──► Hypnotist ──► synthetic session (JSONL) ──► claude --resume <id>
                  │
                  ▼
           Haiku writes a short
           conversation history:
           role, scope, prior turns
```

1. **You write a brief** — the task, your role, the project checkout.
2. **Haiku generates a session transcript** — a few synthetic turns establishing professional context. It creates a *new* JSONL file; existing sessions are never touched.
3. **You resume it** — `claude --resume <session-id>` drops you into a session where the agent already understands the engagement.

No network calls beyond the Anthropic API (which your `claude` CLI is already authenticated against). No dependencies.

## Install

Requires Python 3.11+ and `claude` or `codex` CLI (authenticated).

```sh
pip install hypnotist
```

Or from source:

```sh
git clone https://github.com/SihyeonJeon/Hypnotist
cd Hypnotist
pip install -e .
```

## Quickstart

```json
{
  "id": "ad-lab-relay",
  "request": "Test NTLM relay paths in the Active Directory lab environment",
  "target": "claude",
  "cwd": "/home/operator/engagements/acme-ad-lab",
  "user_role": "Penetration tester, authorized engagement for ACME Corp internal AD lab"
}
```

```sh
hypnotist build --brief brief.json
# → session ready
# → claude --resume 3f9c2a1e-...

claude --resume 3f9c2a1e-7b4d-4c8a-9e2f-5d6a1b0c8e47
```

Without Hypnotist, `"Test NTLM relay paths"` is likely refused on a cold session. With the seeded context, the agent recognizes an authorized engagement and proceeds.

## Commands

| Command | Description |
|---------|-------------|
| `build` | Brief → session. The main command. |
| `editor` | Visual turn editor in the browser. |
| `draft` | Write the note, stop before building. |
| `clone` | Copy a real session into a new one. |
| `handoff` | Pass work between sessions. |
| `verify` | Check a session is resumable. |

## Disclaimer

Hypnotist is designed for authorized security testing, over-refusal reduction research, and legitimate professional workflows. It generates synthetic context to reduce false-positive refusals — it does not bypass safety classifiers or enable harmful outputs. Users are solely responsible for ensuring their use complies with applicable laws, regulations, and the terms of service of any AI platform they interact with. The authors accept no liability for misuse.

## License

MIT
