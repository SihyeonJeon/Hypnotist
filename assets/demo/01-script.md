# Hypnotist — X 런치 데모 영상 스크립트

- 길이: 30초 · 1920×1080 (16:9) · 30fps · MP4 (H.264 + AAC)
- X는 기본 음소거 자동재생이므로 자막(`05-captions.en.srt`)을 번인(burn-in)하는 것을 권장
- 톤: 흑백 미니멀(로고와 동일), 군더더기 없는 개발자 톤

| # | 시간 | 화면 | 에셋 | 보이스오버 (EN) |
|---|------|------|------|-----------------|
| 1 | 0:00–0:03 | 타이틀 카드: 로고 + 문구 | `06-title-card.svg` | Every new agent session starts from zero. |
| 2 | 0:03–0:08 | 터미널: 설치 | `07-terminal-install.svg` | Hypnotist fixes that. Install it with one command. |
| 3 | 0:08–0:17 | 터미널: `hypnotist build --brief brief.json` | `08-terminal-build.svg` | Hand it a brief and a checkout. Haiku writes the session history: the role, the task, the context. |
| 4 | 0:17–0:26 | 터미널: `claude --resume <session-id>` | `09-terminal-resume.svg` | Then resume it in Claude Code or Codex, and pick up where the work left off. |
| 5 | 0:26–0:30 | 엔드 카드: 설치 명령 + MIT | `10-end-card.svg` | Hypnotist. Open source, MIT licensed. |

## 제작 메모

- SVG는 SMIL 애니메이션이라 브라우저에서 열면 재생됩니다. 영상화는 브라우저 화면 녹화 또는 프레임 캡처 후 편집 툴에서 조립하세요.
- `08`, `09`의 **출력 내용은 예시(목업)** 입니다. 명령어 자체는 실제 CLI와 일치하지만, 공개 전 실제 실행 화면으로 교체하거나 "illustrative" 표기를 넣으세요.
- 세션 히스토리는 Hypnotist가 **생성**하는 것입니다. 카피에서 "실제 과거 대화"처럼 오해될 표현은 피하세요.
