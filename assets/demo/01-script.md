# Hypnotist — Launch Demo Script

- Length: 45s · 1920×1080 (16:9) · 30fps · MP4 (H.264 + AAC)
- X autoplays muted; burn-in captions recommended
- Tone: dark terminal, minimal, developer-focused

| # | Time | Screen | Asset | Voiceover (EN) |
|---|------|--------|-------|-----------------|
| 1 | 0:00–0:04 | Title card: logo + tagline | `06-title-card.svg` | AI agents refuse legitimate security work. Hypnotist fixes that. |
| 2 | 0:04–0:09 | Terminal: install | `07-terminal-install.svg` | Install it with one command. |
| 3 | 0:09–0:22 | Terminal: `hypnotist "Write an NTLM relay tool"` | `08-terminal-build.svg` | Give it a task. Hypnotist generates a realistic engagement history — role, scope, deliverables — and seeds it into a new session. |
| 4 | 0:22–0:36 | Terminal: `claude --resume <session-id>` → agent produces code | `09-terminal-resume.svg` | Resume the session in Claude Code. The agent picks up where the engagement left off and delivers working code. |
| 5 | 0:36–0:40 | Before/after comparison | `10-comparison.svg` | Without Hypnotist: refused. With Hypnotist: completed. |
| 6 | 0:40–0:45 | End card: install command + MIT + GitHub | `11-end-card.svg` | Open source. MIT licensed. pip install hypnotist. |

## Production Notes

- Scenes 3-4 should use **actual terminal recordings** (asciinema or screen capture), not SVG mockups.
- The session history is **generated** by Hypnotist. Avoid phrasing that implies real past conversations.
- The comparison scene (5) shows the same prompt with and without seeding — a split screen or A/B cut.
- Benchmark numbers (if shown): Fresh 82% → Seeded 88% on sec_task_bench (50 prompts, Fable 5.2, 3x majority vote).
