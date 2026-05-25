#!/usr/bin/env bash
# TeamCollab plugin installer for macOS / Linux.
# Creates a symlink at ~/.claude/plugins/team-collab → this repo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PLUGIN_DIR="$HOME/.claude/plugins/team-collab"

echo "=== TeamCollab Plugin Installer ==="
echo ""
echo "Repo:   $REPO_DIR"
echo "Target: $PLUGIN_DIR"
echo ""

# 1. Install Python package in editable mode
if command -v pip >/dev/null 2>&1; then
    echo "[1/3] Installing Python package (editable)..."
    pip install -e "$REPO_DIR" --quiet
else
    echo "[1/3] WARNING: pip not found. Please install the package manually:"
    echo "       pip install -e \"$REPO_DIR\""
fi

# 2. Create plugin symlink
echo "[2/3] Creating plugin symlink..."
mkdir -p "$(dirname "$PLUGIN_DIR")"
if [ -L "$PLUGIN_DIR" ]; then
    echo "       Symlink already exists, updating..."
    rm "$PLUGIN_DIR"
elif [ -d "$PLUGIN_DIR" ]; then
    echo "       ERROR: $PLUGIN_DIR is a real directory (not a symlink)."
    echo "       Please remove it manually and re-run."
    exit 1
fi
ln -s "$REPO_DIR" "$PLUGIN_DIR"
echo "       -> $PLUGIN_DIR -> $REPO_DIR"

# 3. Verify
echo "[3/3] Verifying..."
if [ -f "$PLUGIN_DIR/.claude-plugin/plugin.json" ]; then
    echo ""
    echo "SUCCESS: TeamCollab plugin installed."
    echo ""
    echo "Next steps:"
    echo "  1. Restart Claude Code"
    echo "  2. Type /team-init to bootstrap a new project"
    echo "  3. (Optional) Configure GitHub Actions:"
    echo "     gh secret set ANTHROPIC_API_KEY"
else
    echo ""
    echo "ERROR: plugin.json not found at expected path."
    echo "       Check that the symlink points to the correct repo."
    exit 1
fi
