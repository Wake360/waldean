#!/usr/bin/env bash
# Claude Code PostToolUse hook: gate Edit/Write on *.ipynb through `waldean check`.
#
# Reads the hook event JSON on stdin (Claude Code's PostToolUse payload has
# .tool_input.file_path for both Edit and Write). Skips anything that isn't a
# notebook. Otherwise runs `waldean check` and, only on a HIGH finding (waldean exit
# code 2), re-emits the report on stderr and exits 2 — Claude Code's
# block-with-feedback exit code, which sends stderr back to the model so it
# can fix the flagged cell instead of the edit silently landing.
#
# Medium (1) and usage-error (3) exit codes pass through unchanged: Claude
# Code treats any non-zero, non-2 exit as non-blocking (shown to the user,
# work continues).

command -v jq >/dev/null || { echo "waldean-gate: jq is required" >&2; exit 2; }
command -v waldean >/dev/null || { echo "waldean-gate: waldean is not on PATH" >&2; exit 2; }

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

case "$file" in
  *.ipynb) ;;
  *) exit 0 ;;
esac

report=$(waldean check "$file" 2>&1)
code=$?

if [ "$code" -eq 2 ]; then
  printf '%s\n' "$report" >&2
  exit 2
fi

exit "$code"
