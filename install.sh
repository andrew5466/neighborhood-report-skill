#!/usr/bin/env bash
# Install the neighborhood-report skill into Claude Code on this machine.
#   bash install.sh --dry-run    show what would change
#   bash install.sh              copy SKILL.md into ~/.claude/skills/neighborhood-report/
# An existing SKILL.md is kept as SKILL.md.bak-<timestamp>; nothing is deleted.
# The kit scripts run from the vault (Brain/Real Estate/Market Intel/Neighborhood Map Lite/scripts) and use the
# Neighborhood Report Tool next to it for base maps and the Leaflet CSS; this installs only the skill.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="$here/skills/neighborhood-report/SKILL.md"
dst_dir="$HOME/.claude/skills/neighborhood-report"
dry=0; [ "${1:-}" = "--dry-run" ] && dry=1

[ -f "$src" ] || { echo "missing $src"; exit 2; }
if [ -f "$dst_dir/SKILL.md" ] && cmp -s "$src" "$dst_dir/SKILL.md"; then
  echo "Already up to date: $dst_dir/SKILL.md"; exit 0
fi
if [ "$dry" -eq 1 ]; then
  [ -f "$dst_dir/SKILL.md" ] && echo "would back up $dst_dir/SKILL.md"
  echo "would copy $src -> $dst_dir/SKILL.md"; exit 0
fi
mkdir -p "$dst_dir"
if [ -f "$dst_dir/SKILL.md" ]; then
  cp "$dst_dir/SKILL.md" "$dst_dir/SKILL.md.bak-$(date +%Y%m%d-%H%M%S)"
fi
cp "$src" "$dst_dir/SKILL.md"
echo "Installed $dst_dir/SKILL.md"
