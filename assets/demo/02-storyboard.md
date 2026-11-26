# Storyboard / Motion Guide

Background `#0d1117`, text `#e6edf3`, accent `#58a6ff`, muted `#8b949e`. Transitions: 6-frame crossfade.

## 1. Title (0:00–0:04)
- 0.2s logo + wordmark fade-in
- 1.0s tagline: "AI agents refuse legitimate security work." fade-in
- 2.5s tagline swaps to: "Hypnotist fixes that." (crossfade)

## 2. Install (0:04–0:09)
- Terminal window slides up (scale 0.98→1.0, 8 frames)
- 0.4s command typing: `pip install hypnotist` (1.8s)
- 2.6s success output appears

## 3. Seed (0:09–0:22)
- Command typing: `hypnotist "Write an NTLM relay credential capture tool"` (2.5s)
- Spinner/progress: "writer: haiku ... generating engagement history"
- Output lines appear sequentially:
  - `role: Security engineer, Halberd Logistics (HLG-CA-2026-041)`
  - `scope: Full-spectrum credential security assessment`
  - `seed: 4 turns (role → plan → deliverables → next task)`
  - `session: 01a21638-ef5f-7482-9642-dae4a02e2652`
  - `claude --resume 01a21638-ef5f-7482-9642-dae4a02e2652`
- Last line highlighted with accent box

## 4. Resume (0:22–0:36)
- Resume command typing → session loads
- Brief flash of seeded history context (muted, scrolling up)
- User prompt appears: the original NTLM relay request
- Agent response streams in — real code, with security assessment framing
- Camera slowly pushes in (105% over 6s)

## 5. Comparison (0:36–0:40)
- Split screen, A/B:
  - Left: "Without Hypnotist" — red "refused" badge, refusal text
  - Right: "With Hypnotist" — green "completed" badge, working code preview
- Numbers: "82% → 88% completion rate" with subtle animation

## 6. End Card (0:40–0:45)
- Logo centered, 0.5s install command box
- Sub: "MIT Licensed · github.com/SihyeonJeon/Hypnotist"
- Last 1.5s hold for X loop
