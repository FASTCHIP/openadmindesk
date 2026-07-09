# Agent Prompts

Use these prompts when assigning work to a simple LLM agent.

## Start New Work

```text
You are working in this repository. Read AGENTS.md and
docs/agent/CONTEXT_PACK.md first. Then choose the first unchecked task in
docs/ROADMAP.md. Make one small, reviewable change. Update docs/WORKLOG.md and
report the verification command you ran.
```

## Implement One Roadmap Task

```text
Implement only this task: <paste task here>.

Required context:
- AGENTS.md
- docs/agent/CONTEXT_PACK.md
- docs/ARCHITECTURE.md
- docs/requirements/MVP.md

Keep the change small. Do not add unrelated features. Run the smallest useful
check. Update docs/WORKLOG.md.
```

## Fix a Bug

```text
Fix this bug: <describe bug here>.

First reproduce or explain why it cannot be reproduced. Change only the files
needed for the fix. Add or update a test when practical. Update docs/WORKLOG.md
with the cause, fix, and verification result.
```

## Review Before Commit

```text
Review the current git diff. Look for correctness bugs, missing tests, security
risks, and documentation drift. Do not rewrite code unless asked. Report
findings with file paths and exact lines.
```

## Continue After Interruption

```text
Continue the last task. Read docs/WORKLOG.md first, then git status. Do not
assume unfinished changes are yours. Identify the intended task, finish only
that task, run verification, and update docs/WORKLOG.md.
```

