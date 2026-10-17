# Architecture

```
notebook ──> ingest (nbformat) ──> layer A: static detectors ──> report
                                    - libcst def-use dataflow      md / json / sarif
                                    - deterministic, key-free      exit code
                                    - exact cell:line + evidence

             layer B (--llm): LLM narrative detector
             claims <-> computation consistency, closed taxonomy,
             span-grounded, verified by a second provider; fuses with
             layer A candidates (filter + population claim = flag)
```

Leakage, multiple testing and accuracy on imbalanced classes leave a trace in
code and stored outputs, so layer A finds them with a dataflow graph and no
LLM. Layer B handles only whether the prose claims match what the code
computes.

## Narrative layer (experimental)

`waldean check --llm --llm-subscription <notebook>` runs layer B through the
`claude` or `codex` CLI. Its quality gates (G2/G3) never ran, so no
narrative-layer precision or recall is claimed. Without `--llm`, Waldean calls
no LLM.

## Taxonomy

`waldean/core/taxonomy/flaws.yaml` holds every flaw class: definition, book
anchor, mutation recipe and severity. `waldean rules` lists them. Detectors,
prompts and reports read the same file. A new class is a taxonomy record, a
detector and a mutation with a mechanical `verify`; see
[`CONTRIBUTING.md`](../CONTRIBUTING.md).
