---
name: finalize-dev
description: Rebuild Docker, update docs and memory, commit and push
disable-model-invocation: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
---

Finalize the current development session by performing all of these steps in order:

## 1. Rebuild Docker

Run `docker compose up --build -d` from the project root. Verify the build succeeds and all services start.

## 2. Update documentation

Read the current versions of these files and update them to reflect any changes made during this session:

- **BUSINESS_ANALYSIS.md** - Update if added features change what is said here. report the differences.
- **TECHNICAL_PLAN.md** — Update status of items, add new items if features were added
- **CLAUDE.md** — Update architecture/key details sections if anything changed
- **README.md** — Update description, tech stack, or structure if relevant

Only update sections that actually changed. Do not rewrite unchanged content.

## 3. Update memory

Read `~/.claude/projects/-Users-dennisdecoene-Dev-windbased-bikeplanner/memory/MEMORY.md` and update it with any new patterns, architecture changes, or key decisions from this session.

## 4. Commit and push

- Stage all changed files (exclude `.DS_Store` and `.claude/` directory)
- Write a concise commit message following the project's conventional commit style (e.g., `feat:`, `fix:`, `docs:`)
- Do NOT add `Co-Authored-By` to the commit message
- Push to the remote

If there are no changes to commit, say so and skip this step.
