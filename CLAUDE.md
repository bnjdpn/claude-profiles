# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`claude-profiles` is a CLI tool that manages Claude Code configuration profiles per technology stack. It auto-detects project types (Python, TypeScript, Go, Rust, Java, iOS/Swift, Flutter, Android, C++) and generates the corresponding `.claude/` directory structure with CLAUDE.md, rules, skills, settings, and `.mcp.json`.

## Running the tool

```bash
# Run directly
python3 claude_profiles.py detect
python3 claude_profiles.py apply auto --dry-run
python3 claude_profiles.py list

# After installation (via setup.sh)
claude-profiles apply <profile> [--variant <variant>] [--dry-run]
```

There are no tests or linting configured for this project itself. The codebase is a single Python script with zero external dependencies.

## Architecture

**Single-file CLI** (`claude_profiles.py`, ~570 lines): everything lives in one file using only stdlib (`argparse`, `json`, `pathlib`, `shutil`).

**Profile format** (`profiles/*.json`): each JSON file defines a complete Claude Code configuration:
- `mcp_servers` → generates `.mcp.json`
- `claude_md` → generates `.claude/CLAUDE.md`
- `rules` → generates `.claude/rules/<name>.md`
- `skills` → generates `.claude/skills/<name>/SKILL.md`
- `settings` → generates `.claude/settings.json`
- `variants` → framework-specific overrides (e.g., Django vs FastAPI for Python, Maven vs Gradle for Java) that merge/override the base profile

**Key flows:**
- Detection (`detect_project`): ordered list of glob markers in `DETECTION_RULES` — order matters, most specific first (iOS before generic JS)
- Variant detection (`detect_variant`): inspects `package.json` deps, `pyproject.toml` content, or specific files like `manage.py`
- Apply (`apply_profile`): loads profile JSON, resolves variant, merges variant overrides, writes all config files to target directory. Backs up existing `CLAUDE.md` before overwriting.

**Profile resolution**: user profiles in `~/.claude-profiles/` take precedence over built-in `profiles/` directory. `init` command copies built-in profiles to the user directory.

## Language

The UI, comments, and docstrings are in French.
