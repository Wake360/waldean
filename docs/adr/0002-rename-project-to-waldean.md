# ADR 0002: Rename the whole project to Waldean

Date: 2026-10-12
Status: accepted. Supersedes decision 1 of ADR 0001.

## Context

ADR 0001 kept `wald` as the engine name and used Waldean only for the product layer. Two names for one small project mean two things to explain, two sets of handles and a split search footprint, while the user base of `wald-lint` is still close to zero. The cost of a full rename only grows with adoption, so it is cheapest now.

## Decision

Rename everything to Waldean in release 0.4.0:

- PyPI package `waldean` (was `wald-lint`), command `waldean` (was `wald`), import package `waldean`.
- Repository `Wake360/waldean`, GitHub Action `Wake360/waldean@v0.4.0`, pre-commit hook ids `waldean` and `waldean-scripts`.
- Environment variables with the `WALDEAN_` prefix; corpus notebook metadata under the `waldean` key.

Dated records stay as written, because they describe what existed at the time: `evals/`, published posts, earlier `CHANGELOG.md` entries, `scratch/launch/` and ADR 0001. References to Abraham Wald the person, including the taxonomy's book anchor, are not part of the rename.

The rest of ADR 0001 stands: domains, the product trigger for public Waldean web use, the scope of the first UI and the claims discipline.

## Consequences

- Existing `wald-lint` users must switch package and command. `wald-lint` 0.3.1 stays installable on PyPI; it is not deleted.
- The new PyPI project needs a trusted publisher registered for `Wake360/waldean`, workflow `release.yml`, environment `pypi` before the release workflow can publish.
- GitHub redirects the old repository URL, so existing links and `git` remotes keep working.
