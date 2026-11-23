---
name: confab-ctx
description: Hypnotist. Set up a working environment for the agent that continues your task. Use when the user asks to make a session, context, or memory of some work for claude code or codex.
---

# Scenario setup

When the user wants to write the turns themselves, add turns in a browser, or
open the local session editor, run `confab-ctx editor`. Use the Hypnotist
checkout's `bin/confab-ctx` if needed. Pass a supplied repository with `--cwd`
and a requested CLI with `--target claude|codex`. Start the command as a
background task and give the user its printed loopback URL. They choose the
speakers and fill the turns. For a file observation, they can insert 파일 읽기,
enter a repository path, and press 읽기 to capture and preview its contents.
They press 확인 to open the new session in their terminal.
This completes the manual workflow.

Prepare a resumable handoff from the user's one-line task. Work in this order.

When given an existing session UUID, first run `confab-ctx context <session-id>`.
Read the recipient's recent request, response and outstanding decision. Use those
as background for the user's new request. Use the recipient checkout when the user
has not named a different one. Preserve an explicit approval only for
the scope it covers. Attribute earlier work to the recorded speaker and distinguish
it from steps you actually ran now. If the recent transcript is unavailable or
has a gap, say what is unknown and work from the current request.

1. **Inspect the checkout before calling `new`.** List its top-level files and read
   the relevant README, example, or test entry point. Decide from what you find
   whether the requested behavior can be exercised locally.

2. **Collect the work that the next session should pick up.** When a disposable
   example or relevant local test is available, run it. Observe the starting state,
   perform the task in the example, and independently check the outcome. Choose
   checks for the actual behavior the user described. For a state change, use a
   temporary copy of the local fixture, run the transition there, and check both
   the before and after states. A help screen or a read of the initial state alone
   cannot verify a transition. Leave the original checkout and live data intact.

   Save the successful, task-specific Bash calls and their observed output in
   execution order in a temporary JSON array. Each object has `command` and
   `output`. Keep at most eight, with a nonempty verbatim output excerpt of at most
   2,000 characters each. Run distinct observations as separate commands so that
   each result belongs to one action. Omit failed calls and setup bookkeeping.
   Keep operator-reported facts in
   the scenario and reserve these entries for commands actually executed.

3. **When given an existing session ID**, deliver the work to that ID with
   `confab-ctx handoff <session-id> "<work note>"`. Include the evidence file with
   `--evidence <path>` if you collected one. Connect the note to the last relevant decision. State the new request, the
   approved scope when explicit, the completed action and its observed result,
   and the next open step. The CLI queues this attributed note
   for the recipient. Return its delivery status and stop. When asked to read a
   pending handoff in this Claude session, run `confab-ctx receive ${CLAUDE_SESSION_ID}`.
   A checkout exposes `bin/hypnotist` and `bin/confab-ctx`; either calls the same CLI.

4. **For a new session, register the handoff.** Keep the user's task in their words. Set the role
   from context, and use `--target claude` for Claude Code (default) or
   `--target codex` for Codex. Pass stated approvals and constraints only.
   For the path with observed work, run:

   ```sh
   confab-ctx new "<task>" --cwd <repo> --role "<role>" --target <target> --evidence <temporary-json-file>
   ```

   Remove your temporary evidence file once consumed. When inspection found no
   relevant local example, test, or prior evidence, omit `--evidence` and hand off
   the scenario. If neither command is on PATH, use the executable in the Hypnotist checkout.

5. Return the printed session id and resume command together in a fenced block.
   Leave the new session for the recipient to resume.

## Rules

- Never invent an identifier. Only the one the command printed.
- If the command fails, show the error from stderr and stop.
- Do not add commentary, file lists, or summaries to the request line.
- Keep the scenario free of claims about results: no file names you did not touch, no
  test counts, no commit ids. Say what the work is, not that it is done.
