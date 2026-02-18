# SKILLS.md as Canonical Output Format

**Date:** 2026-02-18
**Status:** Approved

## Goal

Change edesto's canonical output from `CLAUDE.md` (Claude Code specific) to `SKILLS.md` (portable) as the primary file, with copies for each AI coding tool's native format.

## Motivation

- Ecosystem alignment: Skills are the modern pattern for AI coding agent extensions
- Cross-tool support: A single portable format that works with Claude Code, Cursor, Codex, and OpenClaw
- `SKILLS.md` is natively understood by OpenClaw and aligns with Claude Code's skill conventions

## Output Files

When `edesto init` runs, it generates 4 files with identical content:

| File | Purpose | Tool |
|---|---|---|
| `SKILLS.md` | Canonical source | OpenClaw native, edesto convention |
| `CLAUDE.md` | Copy | Claude Code native |
| `.cursorrules` | Copy | Cursor native |
| `AGENTS.md` | Copy | OpenAI Codex native |

All files are written to the project root directory.

## CLI Changes

### `edesto init`

- Writes `SKILLS.md` as the primary file
- Creates `CLAUDE.md`, `.cursorrules`, and `AGENTS.md` as copies
- Overwrite prompt checks `SKILLS.md` (the canonical file)
- Output message: "Generated SKILLS.md for {board} on {port}. Also created: CLAUDE.md, .cursorrules, AGENTS.md"

## What Doesn't Change

- Template content (same generic CLAUDE.md template)
- Toolchain system
- Detection system
- Board definitions
- CLI flags (--board, --port, --toolchain)

## Scope

Small change: rename primary output file + add AGENTS.md. No architecture changes.
