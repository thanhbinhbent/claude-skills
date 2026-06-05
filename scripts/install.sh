#!/usr/bin/env bash
# Install skills from this repo into a Claude skills directory.
# Nothing is automatic — you choose the method, the scope, and the path.
#
# Usage:
#   ./scripts/install.sh                   # symlink -> ~/.claude/skills  (global, default)
#   ./scripts/install.sh --project         # symlink -> ./.claude/skills  (current project)
#   ./scripts/install.sh --project DIR     # symlink -> DIR/.claude/skills
#   ./scripts/install.sh --target DIR      # symlink -> DIR
#   ./scripts/install.sh --copy ...        # copy real files instead of symlinks
#   ./scripts/install.sh --uninstall ...   # remove skills from the chosen target
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

METHOD="symlink"   # symlink | copy
TARGET=""
UNINSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --copy)    METHOD="copy"; shift ;;
    --symlink) METHOD="symlink"; shift ;;
    --global)  TARGET="$HOME/.claude/skills"; shift ;;
    --project)
      if [ $# -ge 2 ] && [ "${2#-}" = "$2" ]; then d="$2"; shift 2; else d="$PWD"; shift; fi
      TARGET="$(cd "$d" && pwd)/.claude/skills" ;;
    --target)  TARGET="$2"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
[ -n "$TARGET" ] || TARGET="$HOME/.claude/skills"

# Iterate every skill folder (external first, custom last so custom wins on name clash).
each_skill() {  # calls $1 <skill_dir> <name>
  local base d
  for base in "$REPO_DIR/external-skills" "$REPO_DIR/custom-skills"; do
    [ -d "$base" ] || continue
    for d in "$base"/*/; do
      [ -d "$d" ] && [ -f "${d}SKILL.md" ] || continue
      "$1" "$d" "$(basename "$d")"
    done
  done
}

if [ "$UNINSTALL" = 1 ]; then
  [ -e "$TARGET" ] || { echo "nothing at $TARGET"; exit 0; }
  rm_skill() { rm -rf "$TARGET/$2"; }
  each_skill rm_skill
  echo "Uninstalled skills from $TARGET"
  exit 0
fi

# An old setup may have left ~/.claude/skills as a symlink; we need a real directory.
[ -L "$TARGET" ] && rm -f "$TARGET"
mkdir -p "$TARGET"

put_skill() {
  if [ "$METHOD" = "copy" ]; then
    rm -rf "$TARGET/$2"; cp -R "$1" "$TARGET/$2"
  else
    ln -sfn "$(cd "$1" && pwd)" "$TARGET/$2"
  fi
}
each_skill put_skill

# Symlink mode: drop links whose target no longer exists.
[ "$METHOD" = symlink ] && find "$TARGET" -maxdepth 1 -type l ! -exec test -e {} \; -delete 2>/dev/null || true

n=$(find "$TARGET" -maxdepth 1 -mindepth 1 | wc -l | tr -d ' ')
echo "Installed $n skills ($METHOD) -> $TARGET"
