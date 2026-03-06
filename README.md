# claude-profiles

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://www.python.org)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-green.svg)](#)

**One command to configure [Claude Code](https://docs.anthropic.com/en/docs/claude-code) for your entire stack.**

`claude-profiles` auto-detects your project type and generates the full `.claude/` configuration — MCP servers, rules, skills, settings, and `CLAUDE.md` — so Claude Code understands your stack from the first prompt.

## Features

- **Auto-detection** — identifies your stack from project files (`pyproject.toml`, `*.xcodeproj`, `go.mod`, etc.)
- **Variant-aware** — detects frameworks within stacks (Django vs FastAPI, SwiftUI vs UIKit, Maven vs Gradle)
- **MCP servers** — pre-configures the right MCP servers for your stack (GitHub, Context7, Postgres, XcodeBuildMCP, etc.)
- **Rules & skills** — generates contextual coding rules and slash commands tailored to your language and framework
- **Overlays** — layer additional config on top of any profile (e.g. `+healthkit` for iOS health apps)
- **Sync** — re-apply your profile after upstream updates without losing local changes
- **Customizable** — profiles are plain JSON files, easy to edit or create from scratch

## Comparison

| | `claude-profiles` | Manual config | Copy a CLAUDE.md template |
|---|---|---|---|
| Auto-detection | Detects stack + framework variant | — | — |
| MCP servers | Pre-configured per stack | Set up each one manually | Not included |
| Rules & skills | Generated per language/framework | Write from scratch | Generic, not stack-specific |
| Sync & update | `sync` re-applies without losing local changes | Manual merge | Copy-paste again |
| Setup time | ~5 seconds | 30+ minutes | 5 minutes + manual tweaks |

## Supported Stacks

| Profile | Variants |
|---------|----------|
| Python | Django, FastAPI, Flask, Data Science |
| TypeScript / React | Next.js, React, Vue, Svelte |
| TypeScript / Node | Next.js, API (Express/Fastify/Koa) |
| JavaScript / Node | — |
| Java | Maven, Gradle |
| Go | — |
| Rust | — |
| iOS / Swift | SwiftUI, UIKit, SPM, CocoaPods, HealthKit, Widgets, Multiplatform |
| Flutter / Dart | — |
| Android | — |
| C / C++ | — |

## Quick Start

```bash
git clone https://github.com/bnjdpn/claude-profiles.git
cd claude-profiles
bash setup.sh
```

Then, in any project:

```bash
cd your-project/
claude-profiles apply auto
```

That's it. Claude Code is now configured for your stack.

## What Gets Generated

### Python + FastAPI

```bash
claude-profiles apply python --variant fastapi
```

```
your-project/
├── .mcp.json
└── .claude/
    ├── CLAUDE.md
    ├── CLAUDE.local.md
    ├── settings.json
    ├── rules/
    │   ├── python-conventions.md
    │   ├── testing.md
    │   └── fastapi.md
    └── skills/
        ├── build-and-test/SKILL.md
        └── create-module/SKILL.md
```

**`.mcp.json`** — GitHub, Context7, and Postgres pre-configured:
```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_TOKEN}" }
    },
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "postgres": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": { "DATABASE_URL": "${DATABASE_URL:-postgres://localhost/fastapi_dev}" }
    }
  }
}
```

**`.claude/CLAUDE.md`** — stack-aware instructions for Claude Code:
```markdown
# Projet Python

## Stack
- Language: Python 3.12+
- Package manager: uv / pip / poetry

## Commandes
- Install: `pip install -e '.[dev]'` ou `uv sync`
- Tests: `pytest`
- Lint: `ruff check --fix .`
- Format: `ruff format .`
- Type check: `mypy .`

## Framework: FastAPI
- Dev: `uvicorn app.main:app --reload`
- Docs: http://localhost:8000/docs (Swagger)
- Tests: `pytest`
- Async par défaut
```

### iOS / Swift

```bash
claude-profiles apply ios-swift
```

```
your-project/
├── .mcp.json
└── .claude/
    ├── CLAUDE.md
    ├── CLAUDE.local.md
    ├── settings.json
    ├── rules/
    │   ├── swift-conventions.md
    │   └── project-structure.md
    └── skills/
        ├── build-and-test/SKILL.md
        └── create-feature/SKILL.md
```

**`.mcp.json`** — XcodeBuildMCP for build/test/run, plus GitHub and Context7:
```json
{
  "mcpServers": {
    "xcodebuild": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "xcodebuildmcp@latest"]
    },
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_TOKEN}" }
    },
    "context7": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

**`.claude/CLAUDE.md`** — iOS-specific commands and architecture:
```markdown
# Projet iOS / Swift

## Stack
- Language: Swift 5.9+
- IDE: Xcode 15+
- Deployment target: iOS 17+
- Architecture: MVVM

## Commandes
- Build: `xcodebuild -scheme <scheme> build`
- Tests: `xcodebuild test -scheme <scheme> -destination 'platform=iOS Simulator,name=iPhone 16'`
- Format: `swift format --recursive .`
```

## Commands

```bash
# Detect your project's stack
claude-profiles detect

# Apply the detected profile automatically
claude-profiles apply auto

# Apply a specific profile with a variant
claude-profiles apply python --variant fastapi

# Apply a profile with overlays
claude-profiles apply ios-swift +healthkit +widgets

# Preview changes without writing anything
claude-profiles apply auto --dry-run

# List available profiles
claude-profiles list

# Show profile details
claude-profiles show python

# Show overlay details
claude-profiles show +healthkit

# Compare current config vs a profile
claude-profiles diff auto

# Re-apply profile after upstream updates
claude-profiles sync

# Force sync (overwrite local changes)
claude-profiles sync --force

# Initialize user profiles directory
claude-profiles init

# Create a new custom profile
claude-profiles create my-stack
```

## Overlays

Overlays add configuration on top of any base profile. They're useful for cross-cutting concerns like HealthKit, Firebase, or CI pipelines.

```bash
claude-profiles apply ios-swift +healthkit
```

This merges the `healthkit` overlay into the `ios-swift` profile — adding HealthKit-specific rules, skills, and CLAUDE.md instructions alongside the base iOS configuration.

Overlays live in `~/.claude-profiles/overlays/` and use the same JSON format as profiles.

## Customization

### Local instructions

When a profile is applied, a `.claude/CLAUDE.local.md` file is created if it doesn't exist. This is where you add project-specific instructions — it's included via `@CLAUDE.local.md` at the end of the generated `CLAUDE.md` and is never overwritten by `apply` or `sync`.

This file is git-ignored, so each developer can have their own instructions.

### Custom profiles

Profiles are JSON files in `~/.claude-profiles/`. Run `claude-profiles init` to copy all built-in profiles there, then edit or create new ones.

```bash
# Create a new profile from scratch
claude-profiles create my-stack

# Or copy and modify an existing one
cp ~/.claude-profiles/python.json ~/.claude-profiles/my-python.json
```

User profiles in `~/.claude-profiles/` take precedence over built-in ones.

## How It Works

`claude-profiles` scans your project directory for marker files (`pyproject.toml`, `Package.swift`, `go.mod`, `pom.xml`, etc.) using an ordered detection list — most specific patterns match first. Once the stack is identified, it optionally detects the framework variant by inspecting dependency files. The matched profile JSON is loaded, merged with any requested overlays, and written to your project's `.claude/` directory and `.mcp.json`.

No network calls, no package installation, no magic. Just file generation from JSON templates.

## Requirements

Python 3.10+, standard library only. Zero external dependencies.

## License

[MIT](LICENSE)

---

<sub>See also: [Claude Code native profiles feature request (#7075)](https://github.com/anthropics/claude-code/issues/7075)</sub>
