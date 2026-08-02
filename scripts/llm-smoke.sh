#!/usr/bin/env bash
# Weekly canary for the unpinned claude/codex CLI dependency (the only
# runtime for the narrative layer). Run by absolute path; logs to
# ~/.wald-llm-smoke.log. Schedule (macOS):
#   crontab -e   ->   0 9 * * 1 PATH=/usr/local/bin:$HOME/.local/bin:/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/bin:/bin /Users/filipvachek/wald/scripts/llm-smoke.sh
# Limit: this catches hard envelope breakage (schema change, missing CLI),
# not silent narrative degradation — a schema-valid but empty LLM response
# still leaves the static high finding, rc=2, and logs OK.
set -u
log="$HOME/.wald-llm-smoke.log"
ts=$(date +%Y-%m-%dT%H:%M)
cd "$(dirname "$0")/.." || { echo "$ts FAIL cd" >> "$log"; exit 1; }
out=$(uv run wald check examples/leaky.ipynb --llm --llm-subscription 2>&1)
rc=$?
if [ "$rc" -eq 2 ] && printf '%s' "$out" | grep -q '^# Wald report' && ! printf '%s' "$out" | grep -qi "backend error"; then
    echo "$ts OK rc=$rc" >> "$log"
    exit 0
fi
{
    echo "$ts FAIL rc=$rc"
    printf '%s\n' "$out" | tail -n 5
} >> "$log"
exit 1
