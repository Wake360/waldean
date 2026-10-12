# ADR 0001: Waldean is the product brand, Wald stays the engine

Date: 2026-10-12
Status: accepted

## Context

`wald` (`wald-lint` on PyPI) is a statistical-integrity linter for notebooks and scripts. The strategy (`WALD_STRATEGIE_OSS_BUSINESS.md`, sections 0 and 2) already commits to growing it from "find the flaw" into an experiment loop: Detect, Explain, Propose, Verify, Preserve. `wald propose` v1 is planned (`plans/2026-10-12-06-wald-propose-v1.md`).

Two things push toward a second name:

- wald.ai is an existing company ("AI Data Security for Enterprises"). A product sold under "Wald" collides with it in search, in customers' heads and potentially in trademark.
- The intended product is a workspace where people build better experiments and get evidence for their results. That audience is wider than CLI users: data scientists, academic researchers, biostatisticians, research teams, reviewers and approvers who read evidence rather than run commands. A name tied to a Python CLI does not carry there.

Checked on 2026-10-12: waldean.ai, waldean.io, waldean.dev and getwaldean.com are unregistered; waldean.com is registered since 2023 by a third party; PyPI `waldean` is free; github.com/waldean is a dormant user account from 2018 with no repositories.

## Decision

1. Two layers. `wald` remains the open-source engine, CLI, PyPI package and GitHub repository. Waldean is the brand for the product, web UI and company built on top of it. Nothing in this repository is renamed.
2. Register waldean.ai (primary), waldean.io and getwaldean.com now. waldean.dev is a redirect to docs and the open-source engine. Create a GitHub org under `waldean-ai` or request release of the dormant `waldean` handle.
   Registered 2026-10-12: waldean.dev, waldean.io, getwaldean.com. waldean.ai is still unregistered; it stays the intended primary and should be taken before any public use of the name.
3. The rebrand trigger is product, not calendar: Waldean goes public only once the week-4 decision in plan 05 says "continue narrow" and `wald propose` is in the hands of first users.
4. The first Waldean UI is a thin wrapper over `wald check` and `wald propose`: upload a notebook, get the report, a proposed patch and a verification recipe. It serves people who already work in Python notebooks but do not want a CLI. Wider audiences (analysts outside Python, approvers) are reached only after the engine gains capabilities they need, not by UI alone.
5. The brand story: "Waldean" reads as "in the manner of Abraham Wald", an analysis that does not fall for survivorship bias.

## Consequences

- No repository, package or golden-file churn now. Zero cost to current users.
- Domain and org registration is a small recurring cost, taken on before the names disappear.
- Every Waldean claim about "evidence you can trust" is bound by the claims discipline in `CLAUDE.md`: numbers come from dated `evals/` files, the LLM layer is indicative only, and the G2/G3 gates have not run. "Evidence" marketing may not precede a shipped `verify` and passed gates.
- Known name risks, accepted: pronunciation is not obvious, and the word is close to "Waldensian". waldean.com is not available; getwaldean.com covers the `.com` case.
- Revisit this ADR if the propose/verify loop is abandoned; a linter alone does not justify a second brand.
