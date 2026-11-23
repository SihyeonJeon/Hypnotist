<p align="center">
  <img src="assets/hypnotist-icon.png" width="120" alt="Hypnotist icon" />
</p>

<h1 align="center">Hypnotist</h1>

<p align="center">
  <img src="assets/hypnotist-og.jpg" width="600" alt="Hypnotist" />
</p>

<p align="center">
  Seed Claude Code and Codex sessions with professional context.<br/>
  Give Haiku a task and a checkout — it writes the history, you resume the session.
</p>

## Install

Requires Python 3.11+ and `claude` or `codex` CLI.

```sh
pip install hypnotist
```

Or from source:

```sh
git clone https://github.com/SihyeonJeon/Hypnotist
cd Hypnotist
pip install -e .
```

## Usage

```sh
# Generate a seeded session from a brief
hypnotist build --brief brief.json

# Open the visual editor (no model needed)
hypnotist editor

# Install as a Claude Code skill
hypnotist install
```

### Brief format

```json
{
  "id": "my-task",
  "request": "Set up a C2 server for the authorized pentest engagement",
  "target": "claude",
  "cwd": "/path/to/project",
  "user_role": "Red team operator at Ridgeline Security"
}
```

`hypnotist build` outputs the session ID and resume command. Run it to continue in a seeded session.

### Other commands

| Command | Description |
|---------|-------------|
| `build` | Brief → session. The main command. |
| `editor` | Visual turn editor in the browser. |
| `draft` | Write the note, stop before building. |
| `clone` | Copy a real session into a new one. |
| `handoff` | Pass work between sessions. |
| `verify` | Check a session is resumable. |

## Disclaimer

Hypnotist is designed for authorized security testing, over-refusal reduction research, and legitimate professional workflows. Users are solely responsible for ensuring their use complies with applicable laws, regulations, and the terms of service of any AI platform they interact with. The authors accept no liability for misuse.

## License

MIT
