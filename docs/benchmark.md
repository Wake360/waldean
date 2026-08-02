# Scoring an external tool against the Wald corpus

The mutation corpus is a benchmark: 192 mechanically verified flawed
notebooks plus 83 clean ones (56 synthetic, 27 real and reviewed), each
mutant proven flawed at build time (e.g. a leakage mutant's scaler must
have seen the full row count). Any tool — linter, LLM, agent — can be
scored against it.

## Format

One JSON object. Keys are corpus-relative POSIX paths exactly as they
appear in `corpus/MANIFEST.json` (`clean/...`, `mutated/...`, `real/...`).
Values are lists of findings:

    {
      "mutated/churn-s11__leakage-fit-before-split__m0.ipynb": [
        {"flaw_id": "leakage-fit-before-split", "confidence": 0.9}
      ],
      "clean/churn-s11.ipynb": []
    }

Omitted files mean "no findings". `confidence` defaults to 1.0; findings
below the confidence floor (0.8, wald's own) are not counted for the
static classes but do count for the candidate layer. `flaw_id` values
come from `wald rules --format json`. Unknown file keys are an error.

## Scoring

    wald eval --corpus corpus --predictions preds.json

Scoring reuses wald's own eval code path: a mutant is a TP only if a
finding carries its exact `flaw_id`; any confident finding on a clean
notebook is an FP; confident findings of a *different* class on a mutant
are FPs too. Narrative-only mutants (32 of 192) are excluded from the
static table, same as for wald itself.

## Corpus version

Cite the `built` date plus the `provenance` block from
`corpus/MANIFEST.json`. A rebuilt corpus (`wald corpus build`) with the
same seeds and `WALD_BUILD_DATE` is byte-identical.

## Worked example

`scripts/self-score.sh` feeds wald's own `check --format json` output
through the converter and reproduces `wald eval`'s numbers exactly —
note it concatenates `flags` and `candidates`, since candidate-layer
findings (survivorship) sit below the confidence floor by design.
