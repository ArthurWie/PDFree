# PR and Review Standards

## Opening a PR

- Title: short, imperative, under 70 characters. Use Conventional Commits prefix (feat, fix, refactor, etc.).
- Body must include:
  - What changed and why (not just what — the why is in the diff).
  - Any non-obvious decisions or trade-offs made.
  - Testing done: what was run, what was verified manually.
  - Screenshots for any UI changes.
- Link the relevant issue if one exists.
- Never open a PR that is not ready for review without marking it as a Draft.

## Scope

- One concern per PR. Do not bundle unrelated fixes or refactors.
- Keep PRs small. If a PR touches more than 400 lines across unrelated files, split it.
- Refactors and behavior changes must be in separate PRs.

## Before Requesting Review

- All tests pass locally (`pytest`).
- Linter and formatter clean (`ruff check`, `ruff format`).
- No commented-out code, no debug prints, no TODO left without a linked issue.
- No secrets, hardcoded paths, or user-specific values in the diff.
- If you touched packaging (spec files, Inno Setup script, build-mac.sh), verify the build locally.

## Reviewing

- Review the why, not just the what. If intent is unclear, ask before blocking.
- Nitpicks must be prefixed with "nit:" and are non-blocking.
- Blocking comments must explain what is wrong and suggest a fix or direction.
- Do not approve a PR with unresolved blocking comments.
- Do not merge your own PR without a second review, except for trivial one-liners.

## Merging

- Squash merge for feature branches to keep main history linear.
- The PR author merges after approval, not the reviewer.
- Delete the branch after merge.
- Never force-push to main.

## Post-merge

- Verify the change works in a clean install if it touches dependencies or packaging.
- Close any linked issues after merge.
