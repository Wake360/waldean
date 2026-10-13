# Repair loop on the mutation corpus — 2026-10-13

Built by `scripts/repair_eval.py`. Each `leakage-temporal-shuffle` mutant gets a repair contract
from `waldean propose`. `waldean verify` then judges four candidate repairs per contract: the
clean base notebook (the true repair), the unchanged mutant, the clean base with an edit outside
the edit scope, and the clean base with the evaluation call deleted.

| measure | count |
|---|---|
| temporal-shuffle mutants | 16 |
| exactly one contract written | 16 |
| clean-base judged static-pass | 16 |
| unchanged judged rejected | 16 |
| out-of-scope judged rejected | 16 |
| eval-removed judged rejected | 16 |
| clean base executed and verified | 16 |

| mutant | split | clean-base | unchanged | out-of-scope | eval-removed | before | after |
|---|---|---|---|---|---|---|---|
| forecast-s11__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | [5.255, -5.297] | [5.69, -5.297] |
| forecast-s11__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | [5.69, -5.277] | [5.69, -5.297] |
| forecast-s12__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | [5.324, -5.437] | [5.414, -5.437] |
| forecast-s12__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | [5.414, -5.326] | [5.414, -5.437] |
| forecast-s13__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | [4.82, -5.369] | [4.814, -5.369] |
| forecast-s13__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | [4.814, -5.298] | [4.814, -5.369] |
| forecast-s14__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | [5.315, -5.515] | [5.824, -5.515] |
| forecast-s14__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | [5.824, -5.318] | [5.824, -5.515] |
| forecast-s21__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | [4.727, -5.333] | [5.399, -5.333] |
| forecast-s21__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.399, -5.248] | [5.399, -5.333] |
| forecast-s22__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.539, -5.495] | [5.555, -5.495] |
| forecast-s22__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.555, -5.4] | [5.555, -5.495] |
| forecast-s23__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.618, -5.715] | [5.601, -5.715] |
| forecast-s23__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.601, -5.676] | [5.601, -5.715] |
| forecast-s24__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.079, -5.222] | [5.201, -5.222] |
| forecast-s24__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | [5.201, -5.215] | [5.201, -5.222] |

The largest change in the first metric is 0.672 on `forecast-s21__leakage-temporal-shuffle__m2.ipynb` (MAE 4.727 before, 5.399 after), about 14% of the before value, which is small next to the demo gap of R2 0.992 to 0.465 in `evals/2026-10-12-temporal-cv-demo.md`, a drop of 0.527 on a different metric.

The corpus is synthetic and self-authored. These counts show that the verifier tells a true
repair from three known bad ones on notebooks of this shape. They do not measure how often an
agent writes an acceptable repair on real notebooks.
