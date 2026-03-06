# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`claude-profiles` is a CLI tool that manages Claude Code configuration profiles per technology stack. It auto-detects project types (Python, TypeScript, Go, Rust, Java, iOS/Swift, Flutter, Android, C++) and generates the corresponding `.claude/` directory structure with CLAUDE.md, rules, skills, settings, and `.mcp.json`.

## Running the tool

```bash
# Run directly
python3 claude_profiles.py detect
python3 claude_profiles.py apply auto --dry-run
python3 claude_profiles.py apply ios-swift +healthkit --dry-run
python3 claude_profiles.py list
python3 claude_profiles.py show +healthkit

# After installation (via setup.sh)
claude-profiles apply <profile> [--variant <variant>] [+overlay ...] [--dry-run]
claude-profiles sync                          # Re-applique le profil source
claude-profiles sync --force                  # Écrase les modifications locales
claude-profiles sync --dry-run                # Prévisualise la synchronisation
```

There are no tests or linting configured for this project itself. The codebase is a single Python script with zero external dependencies.

## Architecture

**Single-file CLI** (`claude_profiles.py`, ~750 lines): everything lives in one file using only stdlib (`argparse`, `json`, `pathlib`, `shutil`).

**Profile format** (`profiles/*.json`): each JSON file defines a complete Claude Code configuration:
- `mcp_servers` → generates `.mcp.json`
- `claude_md` → generates `.claude/CLAUDE.md`
- `rules` → generates `.claude/rules/<name>.md`
- `skills` → generates `.claude/skills/<name>/SKILL.md`
- `settings` → generates `.claude/settings.json`
- `variants` → framework-specific overrides (e.g., Django vs FastAPI for Python, Maven vs Gradle for Java) that merge/override the base profile

**Overlay format** (`profiles/overlays/*.json`): same structure as profiles but all fields optional. Adds additive configuration on top of a base profile:
- `compatible_profiles` → optional list of profile names; triggers a warning (not a block) if used with an incompatible profile
- Merge strategy: `mcp_servers`/`rules`/`skills` are dict-merged, `settings` is deep-merged (overlay wins), `claude_md` is appended with `\n\n---\n\n` separator

**Key flows:**
- Detection (`detect_project`): ordered list of glob markers in `DETECTION_RULES` — order matters, most specific first (iOS before generic JS)
- Variant detection (`detect_variant`): inspects `package.json` deps, `pyproject.toml` content, or specific files like `manage.py`
- Apply (`apply_profile`): loads profile JSON, resolves variant, loads overlays, merges everything in order (base → variant → overlays), writes all config files to target directory. Backs up existing `CLAUDE.md` before overwriting.

**Profile/overlay resolution**: user files in `~/.claude-profiles/` (and `~/.claude-profiles/overlays/`) take precedence over built-in directories. `init` command copies both profiles and overlays to the user directory.

## Language

The UI, comments, and docstrings are in French.
