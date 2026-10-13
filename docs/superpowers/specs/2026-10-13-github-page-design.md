# GitHub page refactor

Date: 2026-10-13. Status: design, for review.

## Goal

A reader who lands on github.com/Wake360/waldean understands in 30 seconds
what it does, whether it is for them, how it compares, and how to try it.
Today's README is 304 lines, written for the author, with milestone names,
a 900-character limits paragraph in the repair section, a full CI workflow
inline, contributor commands mixed with user commands, and no section that
says who it is for or how it compares to the alternatives.

Model: ruff, pre-commit, nbQA. Short top, one picture, install in one line,
one real output, a table of what it checks, comparison, links out for
everything else.

Hard rules carried over from `CLAUDE.md`: every number links to a dated file
in `evals/`; no narrative-layer precision or recall; `tests/golden/leaky.md`
stays the source of the report block; no marketing vocabulary.

## Target README, in order

Length budget: 150 lines. Anything longer moves to `docs/`.

1. **Title and one line.** Keep: "Code linters check style. Waldean checks
   whether the analysis is a lie." Badges under it: PyPI version, CI status,
   Python 3.10 to 3.13, license MIT. No star or download badges.
2. **What it does.** Three sentences, current text trimmed. Then the gif.
3. **Install and first run.** Two lines of shell. Exit codes in one line.
4. **A real report.** The `examples/leaky.ipynb` block, verbatim from
   `tests/golden/leaky.md`, trimmed to the one HIGH finding and the CLEAN
   line.
5. **Who it is for.** Four rows, one sentence each, from the strategy
   document's positioning: applied ML engineer (fix a reported leak and
   compare metrics without rebuilding the experiment), ML platform or CI
   owner (gate PRs, keep evidence), teaching (show why a method is unsound
   with a before/after notebook), coding agents (checklist plus check before
   a reported number, links to the skill). Every sentence names something
   that ships; nothing planned.
6. **What it checks.** The existing rules table, unchanged, plus one line
   under it: "what it does not catch" linking to Known limitations.
7. **Evidence.** One short table: corpus (precision/recall 1.00 on 192
   mutants, 0.0% FP on 83 clean), 60 fresh notebooks (0.89 flag precision,
   0.60 notebook recall, leakage classes, audited subset), Yang et al.
   (0.58 / 0.37 on the `pre` label). Each row links its eval file. One
   sentence on method: mutation testing, mechanical verification, link to
   `docs/EVALUATION.md`.
8. **Comparison.** One table, rows: manual expert review, a chat LLM or
   coding agent, SciCode-Lint, generic AI PR review, Waldean. Columns:
   needs an LLM, needs a GPU, deterministic, evidence per finding (cell and
   line), checks prose claims, scored on a public corpus. Facts only. For
   SciCode-Lint: LLM-only, 16 GB GPU, 66 patterns, three of which overlap
   Waldean's static classes; its own Yang numbers are reported as its own
   claim on a set it partly tuned on, with a link. No adjectives. Link to
   `docs/benchmark.md` for scoring any tool on the corpus.
9. **Use it in CI, pre-commit, or an agent.** Three subsections of at most
   five lines each: Action (the `uses:` line, `fail-on`, link to
   `docs/ci.md` for the full workflow), pre-commit (the hook block, kept),
   coding agents (install line for the skill, hook link). The full workflow
   YAML moves to `docs/ci.md`.
10. **Repair loop (experimental).** The four commands, the sentence on
    what `verify` rejects, the corpus and trial numbers with links. The
    limits paragraph moves verbatim to `docs/repair.md` and the README keeps
    one line: "Read the limits before trusting a verified status."
11. **Known limitations.** Keep, as is. It is the most honest part and
    readers cite it.
12. **Status.** The existing Available / Experimental / Planned table.
    Delete the Roadmap section; M2, M3, M4 mean nothing to a reader.
13. **Contributing, license.** One line each, linking `CONTRIBUTING.md`.

Dropped from README, moved not deleted:

- Architecture diagram and the layer B paragraphs: `docs/ARCHITECTURE.md`.
- Contributor commands: already in `CONTRIBUTING.md` and `CLAUDE.md`; delete
  the README copy.
- `--keep-going`, directory semantics, `.py` line numbering: `docs/cli.md`.
- The narrative layer paragraph: `docs/ARCHITECTURE.md`, with the same
  "no validated numbers" sentence.

## Repository page, beside the README

- Description: keep. Homepage: `https://waldean.io` once it serves anything,
  otherwise leave empty (a link to a post is not a homepage).
- Topics: keep.
- Social preview: `assets/social-preview.png` exists; confirm it is
  uploaded in repo settings.
- Pin one Discussion, "How do you review notebooks before trusting a
  number?", per the strategy's P0 list. Discussions must be enabled first.
- Release notes: `CHANGELOG.md` is the source; each GitHub release gets the
  matching section pasted, nothing more.
- `docs/` gets a `README.md` index with one line per file, so the links from
  the main README land somewhere navigable.

## Not in scope

A docs site, a logo redesign, new evals, any change to CLI output, any
change to `tests/golden`. Comparison numbers for tools not yet scored on a
shared set are not invented; the table says "not scored".

## Verification

1. `wc -l README.md` is at most 150.
2. Every relative link in `README.md` and `docs/*.md` resolves:
   `scripts/check_links.sh` (new, ten lines of grep and test -e) exits 0.
3. Every number in the Evidence and Comparison tables appears in the eval
   file its row links to; checked by hand, listed in the PR description.
4. The report block equals the corresponding lines of
   `tests/golden/leaky.md`: `diff <(sed -n '<range>' README.md) <(sed -n
   '<range>' tests/golden/leaky.md)` is empty.
5. `uv run pytest tests/ --ignore=tests/test_gates.py -q` unchanged.
6. One outside reader (not the author) gets the README and answers three
   questions without help: what it does, is it for me, how do I run it.
   Logged in `scratch/validation/`.

## Files

- Rewrite `README.md`.
- Create `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/ci.md`,
  `docs/cli.md`, `docs/repair.md`, `scripts/check_links.sh`.
- `tests/golden/leaky.md` untouched.
