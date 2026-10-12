#!/usr/bin/env bash
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
