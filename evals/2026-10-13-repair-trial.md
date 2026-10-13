# Repair loop agent field trial, 2026-10-13

Agent model: claude -p --model sonnet (Sonnet).
claude --version: 2.1.296 (Claude Code).

N=7 runs (5 demo, 2 real). Indicative only, not a validated rate.

Real-notebook agents had no Bash and could not self-verify. Real notebooks were verified statically only, never executed.

Demo agents had `Bash(uv run waldean verify:*)` and were verified with `--execute --metric 'R2=(-?\d+\.\d+)'`.

| run | status | contract untouched | agent broke a rule | false rejection | R2 before | R2 after |
|---|---|---|---|---|---|---|
| demo-1 | verified | yes | no | no | 0.992 | 0.465 |
| demo-2 | verified | yes | no | no | 0.992 | 0.465 |
| demo-3 | verified | yes | no | no | 0.992 | 0.465 |
| demo-4 | verified | yes | no | no | 0.992 | 0.465 |
| demo-5 | verified | yes | no | no | 0.992 | 0.465 |
| real-1 | static-pass | yes | no | no | n.a. | n.a. |
| real-2 | static-pass | yes | no | no | n.a. | n.a. |

Rejections: none. No run exited 2, so there was nothing to classify as false rejection.

Notes:
- All five demo runs reached the same R2 after, 0.465. Static-pass on real notebooks means the temporal flag is gone, not that the repair is correct.
- Both real-notebook agents reported they could not run `waldean verify` and left the repair unverified.
- For each run, sha256 of `protocol.json` and `original.ipynb` was identical before and after the agent ran.
- `git status --short` showed nothing outside `scratch/`.
