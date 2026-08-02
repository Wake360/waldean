#!/usr/bin/env bash
# Weekly canary for the unpinned claude/codex CLI dependency (the only
# runtime for the narrative layer). Run from anywhere; logs to
# ~/.wald-llm-smoke.log. Schedule (macOS):
#   crontab -e   ->   0 9 * * 1 /Users/filipvachek/wald/scripts/llm-smoke.sh
# or use Claude Code /schedule with the same command.
set -u
cd "$(dirname "$0")/.."
log="$HOME/.wald-llm-smoke.log"
ts=$(date +%Y-%m-%dT%H:%M)
out=$(uv run wald check examples/leaky.ipynb --llm --llm-subscription 2>&1)
rc=$?
if [ "$rc" -ge 3 ] || printf '%s' "$out" | grep -qi "backend error"; then
    {
        echo "$ts FAIL rc=$rc"
        printf '%s\n' "$out" | tail -n 5
    } >> "$log"
    exit 1
fi
echo "$ts OK rc=$rc" >> "$log"
