# Repair loop on the mutation corpus — 2026-10-13

Built by `scripts/repair_eval.py`. Each `leakage-temporal-shuffle` and `leakage-fit-before-split`
mutant gets a repair contract from `waldean propose --diff`. `waldean verify` then judges four
candidate repairs per contract: the clean base notebook (the true repair), the unchanged mutant,
the clean base with an edit outside the edit scope, and the clean base with the evaluation call
deleted. When `propose --diff` wrote a mechanical `patch.diff`, the patch is applied to the
mutant with `patch` and the result is judged as a fifth candidate.

| measure | `leakage-temporal-shuffle` | `leakage-fit-before-split` |
|---|---|---|
| mutants | 16 | 48 |
| exactly one contract written | 16 | 48 |
| clean-base judged static-pass | 16 | 48 |
| unchanged judged rejected | 16 | 48 |
| out-of-scope judged rejected | 16 | 48 |
| eval-removed judged rejected | 16 | 48 |
| patch.diff written | 0 | 24 |
| patched mutant judged static-pass | 0 | 24 |
| clean base executed and verified | 16 | 48 |

| mutant | split | clean-base | unchanged | out-of-scope | eval-removed | patched | before | after |
|---|---|---|---|---|---|---|---|---|
| churn-s11__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.759] | [0.759] |
| churn-s11__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.759] | [0.759] |
| churn-s12__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.838] | [0.838] |
| churn-s12__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.838] | [0.838] |
| churn-s13__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.817] | [0.817] |
| churn-s13__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.817] | [0.817] |
| churn-s14__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.832] | [0.832] |
| churn-s14__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.832] | [0.832] |
| fraud-s11__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.632] | [0.632] |
| fraud-s11__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.632] | [0.632] |
| fraud-s12__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.592] | [0.592] |
| fraud-s12__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.592] | [0.592] |
| fraud-s13__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.593] | [0.593] |
| fraud-s13__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.593] | [0.593] |
| fraud-s14__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.652] | [0.652] |
| fraud-s14__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.652] | [0.652] |
| housing-s11__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.902] | [0.902] |
| housing-s11__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.902] | [0.902] |
| housing-s12__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.883] | [0.883] |
| housing-s12__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.883] | [0.883] |
| housing-s13__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.886] | [0.886] |
| housing-s13__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.886] | [0.886] |
| housing-s14__leakage-fit-before-split__m0.ipynb | dev | static-pass | rejected | rejected | rejected | static-pass | [0.844] | [0.844] |
| housing-s14__leakage-fit-before-split__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [0.844] | [0.844] |
| forecast-s11__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.255, -5.297] | [5.69, -5.297] |
| forecast-s11__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.69, -5.277] | [5.69, -5.297] |
| forecast-s12__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.324, -5.437] | [5.414, -5.437] |
| forecast-s12__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.414, -5.326] | [5.414, -5.437] |
| forecast-s13__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | - | [4.82, -5.369] | [4.814, -5.369] |
| forecast-s13__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [4.814, -5.298] | [4.814, -5.369] |
| forecast-s14__leakage-temporal-shuffle__m0.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.315, -5.515] | [5.824, -5.515] |
| forecast-s14__leakage-temporal-shuffle__m1.ipynb | dev | static-pass | rejected | rejected | rejected | - | [5.824, -5.318] | [5.824, -5.515] |
| churn-s21__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.768] | [0.768] |
| churn-s21__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.768] | [0.768] |
| churn-s22__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.784] | [0.784] |
| churn-s22__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.784] | [0.784] |
| churn-s23__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.797] | [0.797] |
| churn-s23__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.797] | [0.797] |
| churn-s24__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.799] | [0.799] |
| churn-s24__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.799] | [0.799] |
| fraud-s21__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.533] | [0.533] |
| fraud-s21__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.533] | [0.533] |
| fraud-s22__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.635] | [0.635] |
| fraud-s22__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.635] | [0.635] |
| fraud-s23__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.656] | [0.656] |
| fraud-s23__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.656] | [0.656] |
| fraud-s24__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.652] | [0.652] |
| fraud-s24__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.652] | [0.652] |
| housing-s21__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.862] | [0.862] |
| housing-s21__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.862] | [0.862] |
| housing-s22__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.855] | [0.855] |
| housing-s22__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.855] | [0.855] |
| housing-s23__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.881] | [0.881] |
| housing-s23__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.881] | [0.881] |
| housing-s24__leakage-fit-before-split__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | static-pass | [0.886] | [0.886] |
| housing-s24__leakage-fit-before-split__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [0.886] | [0.886] |
| forecast-s21__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [4.727, -5.333] | [5.399, -5.333] |
| forecast-s21__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.399, -5.248] | [5.399, -5.333] |
| forecast-s22__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.539, -5.495] | [5.555, -5.495] |
| forecast-s22__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.555, -5.4] | [5.555, -5.495] |
| forecast-s23__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.618, -5.715] | [5.601, -5.715] |
| forecast-s23__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.601, -5.676] | [5.601, -5.715] |
| forecast-s24__leakage-temporal-shuffle__m2.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.079, -5.222] | [5.201, -5.222] |
| forecast-s24__leakage-temporal-shuffle__m3.ipynb | heldout | static-pass | rejected | rejected | rejected | - | [5.201, -5.215] | [5.201, -5.222] |

The corpus is synthetic and self-authored. These counts show that the verifier tells a true
repair from three known bad ones on notebooks of this shape. They do not measure how often an
agent writes an acceptable repair on real notebooks.
