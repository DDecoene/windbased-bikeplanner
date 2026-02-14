---
name: docker-plan
description: Create a detailed implementation plan and execute it in Docker
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Task
  - AskUserQuestion
---

You are creating a detailed, unambiguous implementation plan for the following task, then handing it off to a Docker-based Claude agent for execution.

**Task:** $ARGUMENTS

## Phase 1: Research

Explore the codebase to understand the current state of relevant files. Use Glob, Grep, Read, and Task (with Explore subagent) as needed. Identify:

- Which files need to be created or modified
- Existing patterns and conventions to follow
- Any dependencies or constraints

## Phase 2: Clarify

Ask the user any clarifying questions using AskUserQuestion. Resolve ALL ambiguity now — the Docker agent cannot ask questions. Cover:

- Design choices (UI style, behavior, naming)
- Scope (what's in, what's out)
- Edge cases or trade-offs

If the task is clear enough, skip this phase.

## Phase 3: Write the plan

Write a detailed implementation plan to `/tmp/claude-plan.md` with this structure:

```markdown
# Implementation Plan: [task title]

## Context
[Brief description of the task and any relevant codebase context]

## Instructions
- You are working on the windbased-bikeplanner project
- Do NOT use AskUserQuestion — all decisions have been made below
- Do NOT use EnterPlanMode — just implement directly
- All frontend text must be in Dutch
- Follow existing code patterns and conventions
- Read CLAUDE.md first for project conventions

## Changes

### [File path 1]
[Exact description of what to change, with code snippets where helpful]

### [File path 2]
[Exact description of what to change, with code snippets where helpful]

[...repeat for all files...]

## Verification
[Steps to verify the implementation is correct — e.g., build commands, checks to run]
```

Make the plan specific enough that another Claude instance can execute it without any ambiguity. Include exact code snippets for non-trivial changes. Reference line numbers or surrounding code for edits.

## Phase 4: Execute in Docker

After saving the plan, run the Docker container in the background:

```bash
docker compose --profile claude run --rm claude \
  --verbose --output-format stream-json \
  -p "$(cat /tmp/claude-plan.md)"
```

Use the Bash tool with `run_in_background: true` for this command.

Tell the user:
- The plan has been saved to `/tmp/claude-plan.md`
- The Docker agent is running in the background
- How to monitor output (the background task output file path)
- Remind them to run `/finalize-dev` when the Docker agent finishes
