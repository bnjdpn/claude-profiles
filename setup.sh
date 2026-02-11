#!/bin/bash
# Installation de claude-profiles
# Usage: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
PROFILES_DIR="$HOME/.claude-profiles"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       claude-profiles — Installation         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Créer le dossier bin si nécessaire
mkdir -p "$INSTALL_DIR"

# 2. Copier le script principal
cp "$SCRIPT_DIR/claude_profiles.py" "$INSTALL_DIR/claude-profiles"
chmod +x "$INSTALL_DIR/claude-profiles"
echo "  ✓ CLI installé dans $INSTALL_DIR/claude-profiles"

# 3. Copier les profils par défaut
if [ -d "$PROFILES_DIR" ]; then
    echo "  ⚠ $PROFILES_DIR existe déjà"
    read -p "    Écraser les profils existants ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "  → Profils conservés"
    else
        cp "$SCRIPT_DIR/profiles/"*.json "$PROFILES_DIR/"
        echo "  ✓ Profils mis à jour dans $PROFILES_DIR"
    fi
else
    mkdir -p "$PROFILES_DIR"
    cp "$SCRIPT_DIR/profiles/"*.json "$PROFILES_DIR/"
    echo "  ✓ Profils installés dans $PROFILES_DIR"
fi

# 4. Vérifier que ~/.local/bin est dans le PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "  ⚠ $INSTALL_DIR n'est pas dans ton PATH."
    echo "    Ajoute cette ligne à ton ~/.zshrc ou ~/.bashrc :"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# 5. Résumé
PROFILE_COUNT=$(ls "$PROFILES_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "  Installation terminée !"
echo "  → $PROFILE_COUNT profils disponibles"
echo ""
echo "  Utilisation :"
echo "    cd ton-projet/"
echo "    claude-profiles detect          # Détecte la stack"
echo "    claude-profiles apply auto      # Applique le profil détecté"
echo "    claude-profiles list            # Liste les profils"
echo ""
