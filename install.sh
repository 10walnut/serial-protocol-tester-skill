#!/usr/bin/env sh
set -eu

target="${1:-codex}"
destination="${2:-}"
source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_name="serial-protocol-assistant"

if [ -z "$destination" ]; then
  case "$target" in
    codex) destination="$HOME/.codex/skills/$skill_name" ;;
    claude) destination="$HOME/.claude/skills/$skill_name" ;;
    workbuddy)
      skill_root=${WORKBUDDY_SKILL_DIRS%%:*}
      if [ -z "${skill_root:-}" ]; then
        echo "Set WORKBUDDY_SKILL_DIRS or pass a destination path." >&2
        exit 2
      fi
      destination="$skill_root/$skill_name"
      ;;
    harness) destination="$(pwd)/skills/$skill_name" ;;
    custom)
      echo "custom requires a destination path as the second argument." >&2
      exit 2
      ;;
    *) echo "Unknown target: $target" >&2; exit 2 ;;
  esac
fi

mkdir -p "$destination/agents" "$destination/references" "$destination/scripts" "$destination/examples"
cp "$source_root/agents/openai.yaml" "$destination/agents/"
cp "$source_root/SKILL.md" "$source_root/LICENSE" "$destination/"
cp "$source_root/references/protocol-script-format.md" "$destination/references/"
cp "$source_root/scripts/protocol_core.py" "$source_root/scripts/validate_protocol.py" "$destination/scripts/"
cp "$source_root/examples/sample_protocol.json" "$destination/examples/"
printf 'Installed %s for %s at %s\n' "$skill_name" "$target" "$destination"
