#!/usr/bin/env python3
"""
claude-profiles: CLI pour gérer les profils de configuration Claude Code par stack.

Détecte automatiquement le type de projet et applique les MCP servers, skills,
rules et settings adaptés. Entièrement configurable via des profils YAML.

Usage:
    claude-profiles detect              # Détecte le type de projet
    claude-profiles apply <profile>     # Applique un profil
    claude-profiles apply auto          # Détecte et applique automatiquement
    claude-profiles list                # Liste les profils disponibles
    claude-profiles show <profile>      # Affiche le détail d'un profil
    claude-profiles init                # Initialise les profils par défaut dans ~/.claude-profiles/
    claude-profiles create <name>       # Crée un nouveau profil personnalisé
    claude-profiles diff                # Compare la config actuelle vs un profil
"""

import argparse
import hashlib
import json
import os
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Couleurs terminal ───────────────────────────────────────────────────────

class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    RESET = "\033[0m"

def styled(text: str, *styles: str) -> str:
    return "".join(styles) + text + Colors.RESET

# ─── Chemins ──────────────────────────────────────────────────────────────────

PROFILES_DIR = Path.home() / ".claude-profiles"
BUILTIN_PROFILES_DIR = Path(__file__).parent / "profiles"
OVERLAYS_DIR = Path.home() / ".claude-profiles" / "overlays"
BUILTIN_OVERLAYS_DIR = Path(__file__).parent / "profiles" / "overlays"

def get_overlays_dir() -> Path:
    """Retourne le dossier des overlays utilisateur, ou les built-in si pas initialisé."""
    if OVERLAYS_DIR.exists():
        return OVERLAYS_DIR
    return BUILTIN_OVERLAYS_DIR

def get_profiles_dir() -> Path:
    """Retourne le dossier des profils utilisateur, ou les built-in si pas initialisé."""
    if PROFILES_DIR.exists():
        return PROFILES_DIR
    return BUILTIN_PROFILES_DIR

# ─── Applied-profile (métadonnées d'application) ─────────────────────────────

APPLIED_PROFILE_PATH = ".claude/.applied-profile"

def sha256_file(filepath: Path) -> str:
    """Calcule le checksum SHA256 d'un fichier."""
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def read_applied_profile(directory: str = ".") -> Optional[dict]:
    """Lit le fichier .applied-profile s'il existe."""
    ap_path = Path(directory).resolve() / APPLIED_PROFILE_PATH
    if ap_path.exists():
        try:
            return json.loads(ap_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def write_applied_profile(directory: str, profile_name: str, variant: Optional[str],
                          overlays: list[str], generated_files: list[Path]):
    """Écrit le fichier .applied-profile avec les métadonnées et checksums."""
    path = Path(directory).resolve()
    checksums = {}
    for fp in generated_files:
        if fp.exists():
            rel = str(fp.relative_to(path))
            checksums[rel] = sha256_file(fp)

    data = {
        "profile": profile_name,
        "variant": variant,
        "overlays": overlays,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "checksums": checksums,
    }
    ap_path = path / APPLIED_PROFILE_PATH
    ap_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ─── Chargement YAML simplifié (sans dépendance) ─────────────────────────────

def load_profile(name: str) -> dict:
    """Charge un profil depuis le dossier de profils."""
    profiles_dir = get_profiles_dir()
    profile_path = profiles_dir / f"{name}.json"
    if not profile_path.exists():
        print(styled(f"Profil '{name}' introuvable dans {profiles_dir}", Colors.RED))
        print(f"Profils disponibles : {', '.join(list_profiles())}")
        sys.exit(1)
    with open(profile_path) as f:
        return json.load(f)


def list_profiles() -> list[str]:
    """Liste tous les profils disponibles."""
    profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        return []
    return sorted([
        p.stem for p in profiles_dir.glob("*.json")
        if not p.name.startswith("_")
    ])


def deep_merge(base: dict, override: dict) -> dict:
    """Fusionne récursivement deux dicts. override gagne en cas de conflit."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_overlay(name: str) -> dict:
    """Charge un overlay depuis le dossier d'overlays."""
    for overlays_dir in [OVERLAYS_DIR, BUILTIN_OVERLAYS_DIR]:
        overlay_path = overlays_dir / f"{name}.json"
        if overlay_path.exists():
            with open(overlay_path) as f:
                return json.load(f)
    print(styled(f"Overlay '{name}' introuvable.", Colors.RED))
    print(f"Overlays disponibles : {', '.join(list_overlays())}")
    sys.exit(1)


def list_overlays() -> list[str]:
    """Liste tous les overlays disponibles."""
    seen = set()
    overlays = []
    for overlays_dir in [OVERLAYS_DIR, BUILTIN_OVERLAYS_DIR]:
        if overlays_dir.exists():
            for p in overlays_dir.glob("*.json"):
                if not p.name.startswith("_") and p.stem not in seen:
                    seen.add(p.stem)
                    overlays.append(p.stem)
    return sorted(overlays)

# ─── Détection automatique du projet ─────────────────────────────────────────

DETECTION_RULES = [
    # (marqueurs, profil, variante)
    # Ordre important : du plus spécifique au plus générique

    # iOS / Swift — marqueurs très spécifiques
    (["*.xcodeproj", "*.xcworkspace", "Package.swift"], "ios-swift", None),
    # Flutter / Dart — pubspec.yaml est unique à Dart
    (["pubspec.yaml"], "flutter", None),
    # Android — doit avoir app/build.gradle* (sous-dossier app) pour se distinguer de Java
    (["app/build.gradle*", "app/build.gradle.kts"], "android", None),
    # Java — Maven (pom.xml est sans ambiguïté)
    (["pom.xml"], "java", "maven"),
    # Java — Gradle (après Android, donc seulement si pas de app/)
    (["build.gradle", "build.gradle.kts", "gradlew"], "java", "gradle"),
    # Rust
    (["Cargo.toml"], "rust", None),
    # Go
    (["go.mod"], "go", None),
    # TypeScript / React — marqueurs spécifiques React (tsx, next.config)
    (["next.config.*", "*.tsx"], "typescript-react", None),
    # TypeScript / Node — tsconfig sans tsx = probablement backend
    (["tsconfig.json"], "typescript-node", None),
    # JavaScript / Node
    (["package.json"], "javascript-node", None),
    # Python
    (["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"], "python", None),
    # C / C++
    (["CMakeLists.txt", "Makefile"], "cpp", None),
]


def detect_project(directory: str = ".") -> list[tuple[str, Optional[str]]]:
    """Détecte le(s) type(s) de projet dans le répertoire donné."""
    path = Path(directory).resolve()
    detected = []

    for markers, profile, variant in DETECTION_RULES:
        for marker in markers:
            matches = list(path.glob(marker))
            if matches:
                entry = (profile, variant)
                if entry not in detected:
                    detected.append(entry)
                break

    return detected


def detect_variant(profile_name: str, directory: str = ".") -> Optional[str]:
    """Détecte la variante spécifique d'un profil (ex: maven vs gradle pour Java)."""
    path = Path(directory).resolve()

    if profile_name == "java":
        if list(path.glob("pom.xml")):
            return "maven"
        if list(path.glob("build.gradle")) or list(path.glob("build.gradle.kts")) or list(path.glob("gradlew")):
            return "gradle"

    if profile_name in ("typescript-react", "typescript-node", "javascript-node"):
        pkg_path = path / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    return "nextjs"
                if "react" in deps:
                    return "react"
                if "vue" in deps:
                    return "vue"
                if "svelte" in deps or "@sveltejs/kit" in deps:
                    return "svelte"
                if "express" in deps or "fastify" in deps or "koa" in deps:
                    return "api"
            except (json.JSONDecodeError, KeyError):
                pass

    if profile_name == "python":
        if list(path.glob("manage.py")):
            return "django"
        if list(path.glob("app.py")) or list(path.glob("wsgi.py")):
            return "flask"
        if (path / "pyproject.toml").exists():
            content = (path / "pyproject.toml").read_text()
            if "fastapi" in content.lower():
                return "fastapi"

    return None

# ─── Application d'un profil ─────────────────────────────────────────────────

def apply_profile(profile_name: str, variant: Optional[str] = None, directory: str = ".",
                   dry_run: bool = False, overlays: Optional[list[str]] = None):
    """Applique un profil au répertoire courant."""
    profile = load_profile(profile_name)
    path = Path(directory).resolve()
    generated_files: list[Path] = []

    # Résoudre la variante
    if variant is None:
        variant = detect_variant(profile_name, directory)

    if overlays is None:
        overlays = []

    # Charger et valider les overlays
    loaded_overlays: list[tuple[str, dict]] = []
    for overlay_name in overlays:
        overlay = load_overlay(overlay_name)
        # Warning de compatibilité
        compatible = overlay.get("compatible_profiles", [])
        if compatible and profile_name not in compatible:
            print(styled(
                f"  ⚠ overlay '{overlay_name}' est prévu pour {', '.join(compatible)}, "
                f"appliqué sur {profile_name}",
                Colors.YELLOW
            ))
        loaded_overlays.append((overlay_name, overlay))

    variant_config = {}
    if variant and "variants" in profile:
        variant_config = profile["variants"].get(variant, {})

    display_name = profile.get("display_name", profile_name)
    if variant:
        display_name += f" ({variant})"
    if overlays:
        display_name += " " + " ".join(f"+{o}" for o in overlays)

    print(styled(f"\n{'=' * 60}", Colors.BLUE))
    print(styled(f"  Profil : {display_name}", Colors.BOLD, Colors.CYAN))
    print(styled(f"  Cible  : {path}", Colors.DIM))
    print(styled(f"{'=' * 60}\n", Colors.BLUE))

    if dry_run:
        print(styled("  [MODE DRY-RUN] Aucun fichier ne sera modifié\n", Colors.YELLOW))

    # 1. Créer la structure .claude/
    dirs_to_create = [".claude/rules", ".claude/skills"]
    for d in dirs_to_create:
        target = path / d
        if not target.exists():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            print(styled(f"  + mkdir {d}/", Colors.GREEN))

    # 2. Générer .mcp.json
    mcp_servers = {**profile.get("mcp_servers", {})}
    # Fusionner les MCP de la variante
    if variant_config.get("mcp_servers"):
        mcp_servers.update(variant_config["mcp_servers"])
    # Retirer les MCP exclus par la variante
    for excluded in variant_config.get("exclude_mcps", []):
        mcp_servers.pop(excluded, None)

    # Fusionner les MCP des overlays
    for _, overlay in loaded_overlays:
        if overlay.get("mcp_servers"):
            mcp_servers.update(overlay["mcp_servers"])

    if mcp_servers:
        mcp_json = {"mcpServers": mcp_servers}
        mcp_path = path / ".mcp.json"
        if not dry_run:
            mcp_path.write_text(json.dumps(mcp_json, indent=2) + "\n")
            generated_files.append(mcp_path)
        print(styled(f"  + .mcp.json", Colors.GREEN) + f" ({len(mcp_servers)} serveurs MCP)")
        for name in mcp_servers:
            print(styled(f"      - {name}", Colors.DIM))

    # 3. Générer CLAUDE.md
    claude_md = profile.get("claude_md", "")
    if variant_config.get("claude_md_append"):
        claude_md += "\n\n" + variant_config["claude_md_append"]

    # Ajouter le claude_md des overlays
    for overlay_name, overlay in loaded_overlays:
        if overlay.get("claude_md"):
            claude_md += "\n\n---\n\n" + overlay["claude_md"]

    if claude_md:
        claude_md_path = path / ".claude" / "CLAUDE.md"
        if claude_md_path.exists():
            print(styled(f"  ~ .claude/CLAUDE.md existe déjà, sauvegarde en .claude/CLAUDE.md.bak", Colors.YELLOW))
            if not dry_run:
                shutil.copy2(claude_md_path, claude_md_path.with_suffix(".md.bak"))
        if not dry_run:
            claude_md_path.write_text(claude_md + "\n")
            generated_files.append(claude_md_path)
        print(styled(f"  + .claude/CLAUDE.md", Colors.GREEN))

    # 4. Générer les rules
    rules = {**profile.get("rules", {})}
    if variant_config.get("rules"):
        rules.update(variant_config["rules"])

    # Fusionner les rules des overlays
    for _, overlay in loaded_overlays:
        if overlay.get("rules"):
            rules.update(overlay["rules"])

    for rule_name, rule_content in rules.items():
        rule_path = path / ".claude" / "rules" / f"{rule_name}.md"
        if not dry_run:
            rule_path.write_text(rule_content + "\n")
            generated_files.append(rule_path)
        print(styled(f"  + .claude/rules/{rule_name}.md", Colors.GREEN))

    # 5. Générer les skills
    skills = {**profile.get("skills", {})}
    if variant_config.get("skills"):
        skills.update(variant_config["skills"])

    # Fusionner les skills des overlays
    for _, overlay in loaded_overlays:
        if overlay.get("skills"):
            skills.update(overlay["skills"])

    for skill_name, skill_content in skills.items():
        skill_dir = path / ".claude" / "skills" / skill_name
        if not dry_run:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text(skill_content + "\n")
            generated_files.append(skill_path)
        print(styled(f"  + .claude/skills/{skill_name}/SKILL.md", Colors.GREEN))

    # 6. Générer settings.json
    settings = profile.get("settings", {})
    if variant_config.get("settings_merge"):
        # Fusion simple (1 niveau)
        for key, val in variant_config["settings_merge"].items():
            if isinstance(val, dict) and isinstance(settings.get(key), dict):
                settings[key] = {**settings[key], **val}
            else:
                settings[key] = val

    # Deep-merge les settings des overlays
    for _, overlay in loaded_overlays:
        if overlay.get("settings"):
            settings = deep_merge(settings, overlay["settings"])

    if settings:
        settings_path = path / ".claude" / "settings.json"
        if not dry_run:
            settings_path.write_text(json.dumps(settings, indent=2) + "\n")
            generated_files.append(settings_path)
        print(styled(f"  + .claude/settings.json", Colors.GREEN))

    # 7. Écrire .applied-profile
    if not dry_run and generated_files:
        write_applied_profile(directory, profile_name, variant, overlays, generated_files)
        print(styled(f"  + .claude/.applied-profile", Colors.GREEN) + f" ({len(generated_files)} checksums)")

    # 8. Mettre à jour .gitignore
    gitignore_entries = [
        ".claude/settings.local.json",
        ".claude/CLAUDE.local.md",
        ".claude/.applied-profile",
    ]
    gitignore_path = path / ".gitignore"
    existing_gitignore = ""
    if gitignore_path.exists():
        existing_gitignore = gitignore_path.read_text()

    new_entries = [e for e in gitignore_entries if e not in existing_gitignore]
    if new_entries:
        if not dry_run:
            with open(gitignore_path, "a") as f:
                f.write("\n# Claude Code (local)\n")
                for entry in new_entries:
                    f.write(entry + "\n")
        print(styled(f"  + .gitignore (ajout entrées Claude)", Colors.GREEN))

    print(styled(f"\n  Profil '{display_name}' appliqué avec succès !", Colors.BOLD, Colors.GREEN))
    print(styled(f"  Tu peux personnaliser avec .claude/CLAUDE.local.md et .claude/settings.local.json\n", Colors.DIM))

# ─── Commandes CLI ────────────────────────────────────────────────────────────

def cmd_detect(args):
    """Commande: détecter le type de projet."""
    detected = detect_project(args.directory)
    if not detected:
        print(styled("Aucun type de projet détecté dans ce répertoire.", Colors.YELLOW))
        print("Utilise `claude-profiles list` pour voir les profils disponibles.")
        return

    print(styled("\nProjets détectés :\n", Colors.BOLD))
    for profile, variant in detected:
        auto_variant = variant or detect_variant(profile, args.directory)
        label = profile
        if auto_variant:
            label += styled(f" ({auto_variant})", Colors.DIM)
        print(f"  {styled('>', Colors.CYAN)} {label}")

    if len(detected) == 1:
        profile, variant = detected[0]
        auto_variant = variant or detect_variant(profile, args.directory)
        v_str = f" --variant {auto_variant}" if auto_variant else ""
        print(styled(f"\nAppliquer : claude-profiles apply {profile}{v_str}\n", Colors.DIM))


def cmd_list(args):
    """Commande: lister les profils."""
    profiles = list_profiles()
    if not profiles:
        print(styled("Aucun profil trouvé. Lance `claude-profiles init` d'abord.", Colors.YELLOW))
        return

    print(styled("\nProfils disponibles :\n", Colors.BOLD))
    for name in profiles:
        try:
            profile = load_profile(name)
            display = profile.get("display_name", name)
            desc = profile.get("description", "")
            variants = list(profile.get("variants", {}).keys())
            variants_str = ""
            if variants:
                variants_str = styled(f"  variantes: {', '.join(variants)}", Colors.DIM)
            print(f"  {styled(name, Colors.CYAN):30s} {display} — {desc}")
            if variants_str:
                print(f"  {' ' * 30} {variants_str}")
        except Exception:
            print(f"  {styled(name, Colors.RED):30s} (erreur de chargement)")
    print()


def cmd_show(args):
    """Commande: afficher le détail d'un profil."""
    profile = load_profile(args.profile)
    display = profile.get("display_name", args.profile)
    desc = profile.get("description", "")

    print(styled(f"\n{'=' * 60}", Colors.BLUE))
    print(styled(f"  {display}", Colors.BOLD, Colors.CYAN))
    print(styled(f"  {desc}", Colors.DIM))
    print(styled(f"{'=' * 60}\n", Colors.BLUE))

    # MCP Servers
    mcps = profile.get("mcp_servers", {})
    if mcps:
        print(styled("  MCP Servers :", Colors.BOLD))
        for name, config in mcps.items():
            stype = config.get("type", "stdio")
            print(f"    {styled(name, Colors.GREEN):25s} ({stype})")
        print()

    # Variantes
    variants = profile.get("variants", {})
    if variants:
        print(styled("  Variantes :", Colors.BOLD))
        for vname, vconfig in variants.items():
            extra_mcps = list(vconfig.get("mcp_servers", {}).keys())
            excluded = vconfig.get("exclude_mcps", [])
            info_parts = []
            if extra_mcps:
                info_parts.append(f"+MCP: {', '.join(extra_mcps)}")
            if excluded:
                info_parts.append(f"-MCP: {', '.join(excluded)}")
            info = " | ".join(info_parts) if info_parts else ""
            print(f"    {styled(vname, Colors.MAGENTA):20s} {info}")
        print()

    # Rules
    rules = profile.get("rules", {})
    if rules:
        print(styled("  Rules :", Colors.BOLD))
        for rname in rules:
            print(f"    {styled(rname + '.md', Colors.GREEN)}")
        print()

    # Skills
    skills = profile.get("skills", {})
    if skills:
        print(styled("  Skills :", Colors.BOLD))
        for sname in skills:
            print(f"    {styled('/' + sname, Colors.GREEN)}")
        print()


def cmd_apply(args):
    """Commande: appliquer un profil."""
    profile_name = args.profile
    variant = args.variant
    directory = args.directory

    # Parser les overlays (+nom)
    overlay_names = []
    for o in args.overlays:
        name = o.lstrip("+")
        if not name:
            print(styled(f"Nom d'overlay invalide : '{o}'", Colors.RED))
            sys.exit(1)
        overlay_names.append(name)

    if profile_name == "auto":
        detected = detect_project(directory)
        if not detected:
            print(styled("Impossible de détecter le type de projet.", Colors.RED))
            print("Utilise `claude-profiles list` pour voir les profils disponibles.")
            sys.exit(1)
        profile_name, variant = detected[0]
        if variant is None:
            variant = detect_variant(profile_name, directory)
        print(styled(f"  Auto-détecté : {profile_name}" + (f" ({variant})" if variant else ""), Colors.CYAN))

    apply_profile(profile_name, variant, directory, dry_run=args.dry_run, overlays=overlay_names)


def cmd_init(args):
    """Commande: initialiser les profils dans ~/.claude-profiles/."""
    if PROFILES_DIR.exists() and not args.force:
        print(styled(f"{PROFILES_DIR} existe déjà. Utilise --force pour écraser.", Colors.YELLOW))
        return

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # Copier les profils built-in
    for profile_file in BUILTIN_PROFILES_DIR.glob("*.json"):
        dest = PROFILES_DIR / profile_file.name
        shutil.copy2(profile_file, dest)
        print(styled(f"  + {profile_file.name}", Colors.GREEN))

    print(styled(f"\nProfils initialisés dans {PROFILES_DIR}", Colors.BOLD, Colors.GREEN))
    print(styled(f"Tu peux les personnaliser en éditant les fichiers JSON.\n", Colors.DIM))


def cmd_diff(args):
    """Commande: comparer la config actuelle avec un profil."""
    profile_name = args.profile
    directory = args.directory
    path = Path(directory).resolve()

    # Lire le profil appliqué s'il existe
    applied = read_applied_profile(directory)

    if profile_name == "auto":
        if applied:
            profile_name = applied["profile"]
            print(styled(f"  Profil appliqué détecté : {profile_name}", Colors.CYAN))
            if applied.get("variant"):
                print(styled(f"  Variante : {applied['variant']}", Colors.CYAN))
            if applied.get("overlays"):
                print(styled(f"  Overlays : {', '.join(applied['overlays'])}", Colors.CYAN))
        else:
            detected = detect_project(directory)
            if not detected:
                print(styled("Impossible de détecter le type de projet.", Colors.RED))
                sys.exit(1)
            profile_name = detected[0][0]

    profile = load_profile(profile_name)

    print(styled(f"\nComparaison avec le profil '{profile_name}' :\n", Colors.BOLD))

    # Vérifier les checksums si .applied-profile existe
    if applied and applied.get("checksums"):
        modified = []
        for rel_path, expected_hash in applied["checksums"].items():
            fp = path / rel_path
            if not fp.exists():
                modified.append((rel_path, "supprimé"))
            elif sha256_file(fp) != expected_hash:
                modified.append((rel_path, "modifié"))
        if modified:
            print(styled("  Fichiers modifiés depuis l'apply :", Colors.YELLOW))
            for rel, status in modified:
                print(f"    ~ {rel} ({status})")
        else:
            print(styled("  Checksums : OK (aucune modification locale)", Colors.GREEN))
        print()

    # Vérifier .mcp.json
    mcp_path = path / ".mcp.json"
    if mcp_path.exists():
        current_mcps = json.loads(mcp_path.read_text()).get("mcpServers", {})
        profile_mcps = profile.get("mcp_servers", {})
        missing = set(profile_mcps.keys()) - set(current_mcps.keys())
        extra = set(current_mcps.keys()) - set(profile_mcps.keys())
        if missing:
            print(styled("  MCP manquants :", Colors.RED))
            for m in missing:
                print(f"    - {m}")
        if extra:
            print(styled("  MCP supplémentaires (perso) :", Colors.CYAN))
            for m in extra:
                print(f"    + {m}")
        if not missing and not extra:
            print(styled("  MCP : OK (identiques)", Colors.GREEN))
    else:
        print(styled("  .mcp.json absent", Colors.RED))

    # Vérifier les rules
    rules_dir = path / ".claude" / "rules"
    profile_rules = set(profile.get("rules", {}).keys())
    existing_rules = set()
    if rules_dir.exists():
        existing_rules = {p.stem for p in rules_dir.glob("*.md")}
    missing_rules = profile_rules - existing_rules
    if missing_rules:
        print(styled("  Rules manquantes :", Colors.RED))
        for r in missing_rules:
            print(f"    - {r}.md")

    # Vérifier les skills
    skills_dir = path / ".claude" / "skills"
    profile_skills = set(profile.get("skills", {}).keys())
    existing_skills = set()
    if skills_dir.exists():
        existing_skills = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    missing_skills = profile_skills - existing_skills
    if missing_skills:
        print(styled("  Skills manquantes :", Colors.RED))
        for s in missing_skills:
            print(f"    - /{s}")

    print()


# ─── Parser CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="claude-profiles",
        description="Gestionnaire de profils Claude Code par stack technique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  claude-profiles detect                     # Détecte le type de projet
  claude-profiles apply ios-swift            # Applique le profil iOS/Swift
  claude-profiles apply java --variant gradle # Java avec Gradle
  claude-profiles apply auto                 # Détecte et applique auto
  claude-profiles apply auto --dry-run       # Prévisualise sans modifier
  claude-profiles apply ios-swift +healthkit   # Profil iOS + overlay HealthKit
  claude-profiles apply ios-swift +healthkit +widgets  # Composition multi-overlays
  claude-profiles list                       # Liste les profils disponibles
  claude-profiles show python                # Détail du profil Python
  claude-profiles init                       # Initialise ~/.claude-profiles/
  claude-profiles diff auto                  # Compare config actuelle vs profil
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Commande à exécuter")

    # detect
    p_detect = subparsers.add_parser("detect", help="Détecter le type de projet")
    p_detect.add_argument("-d", "--directory", default=".", help="Répertoire du projet")
    p_detect.set_defaults(func=cmd_detect)

    # list
    p_list = subparsers.add_parser("list", help="Lister les profils disponibles")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser("show", help="Afficher le détail d'un profil")
    p_show.add_argument("profile", help="Nom du profil")
    p_show.set_defaults(func=cmd_show)

    # apply
    p_apply = subparsers.add_parser("apply", help="Appliquer un profil au projet")
    p_apply.add_argument("profile", help="Nom du profil (ou 'auto')")
    p_apply.add_argument("--variant", "-v", help="Variante spécifique (ex: gradle, maven)")
    p_apply.add_argument("--directory", "-d", default=".", help="Répertoire du projet")
    p_apply.add_argument("--dry-run", action="store_true", help="Prévisualiser sans modifier")
    p_apply.add_argument("overlays", nargs="*", default=[],
                         help="Overlays additifs (ex: +healthkit +widgets)")
    p_apply.set_defaults(func=cmd_apply)

    # init
    p_init = subparsers.add_parser("init", help="Initialiser les profils par défaut")
    p_init.add_argument("--force", action="store_true", help="Écraser les profils existants")
    p_init.set_defaults(func=cmd_init)

    # diff
    p_diff = subparsers.add_parser("diff", help="Comparer la config actuelle vs un profil")
    p_diff.add_argument("profile", help="Nom du profil (ou 'auto')")
    p_diff.add_argument("--directory", "-d", default=".", help="Répertoire du projet")
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
