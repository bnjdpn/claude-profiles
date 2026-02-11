# claude-profiles

CLI pour configurer automatiquement [Claude Code](https://claude.ai/code) selon la stack technique de ton projet.

Détecte le type de projet, puis génère la config complète : MCP servers, rules, skills, settings et CLAUDE.md.

## Profils disponibles

| Profil | Variantes |
|--------|-----------|
| Python | Django, FastAPI, Flask, Data Science |
| TypeScript / React | Next.js, React, Vue, Svelte |
| TypeScript / Node | Next.js, API (Express/Fastify/Koa) |
| JavaScript / Node | — |
| Java | Maven, Gradle |
| Go | — |
| Rust | — |
| iOS / Swift | — |
| Flutter / Dart | — |
| Android | — |
| C / C++ | — |

## Installation

```bash
git clone https://github.com/bnjdpn/claude-profiles.git
cd claude-profiles
bash setup.sh
```

Le script installe la CLI dans `~/.local/bin/` et copie les profils dans `~/.claude-profiles/`.

## Utilisation

```bash
# Détecter la stack du projet courant
claude-profiles detect

# Appliquer automatiquement le bon profil
claude-profiles apply auto

# Appliquer un profil spécifique avec variante
claude-profiles apply python --variant fastapi

# Prévisualiser sans rien modifier
claude-profiles apply auto --dry-run

# Lister les profils disponibles
claude-profiles list

# Voir le détail d'un profil
claude-profiles show python

# Comparer la config actuelle vs un profil
claude-profiles diff auto
```

## Ce qui est généré

Quand tu appliques un profil, `claude-profiles` crée dans ton projet :

```
.mcp.json                        # Serveurs MCP (GitHub, Context7, DB, etc.)
.claude/
  CLAUDE.md                      # Instructions pour Claude Code
  settings.json                  # Permissions (allow/deny)
  rules/                         # Règles contextuelles par type de fichier
    python-conventions.md
    testing.md
  skills/                        # Commandes slash personnalisées
    build-and-test/SKILL.md
    create-module/SKILL.md
```

## Personnalisation

Les profils sont des fichiers JSON dans `~/.claude-profiles/`. Tu peux les modifier ou en créer de nouveaux.

Après application d'un profil, tu peux ajouter des overrides locaux (non versionnés) :
- `.claude/CLAUDE.local.md` — instructions supplémentaires
- `.claude/settings.local.json` — settings locaux

## Zéro dépendance

Python 3.10+ uniquement, stdlib only.
