#!/usr/bin/env bash
status=0
for f in README.md docs/*.md skills/*/SKILL.md; do
  dir=$(dirname "$f")
  grep -oE '\]\([^)#]+' "$f" | sed 's/^](//' | while read -r link; do
    case "$link" in
      https://github.com/Wake360/waldean/blob/*/*) path=${link#https://github.com/Wake360/waldean/blob/*/} ;;
      http*) continue ;;
      *) path="$dir/$link" ;;
    esac
    [ -e "$path" ] || { echo "$f: $link"; exit 1; }
  done || status=1
done
exit $status
