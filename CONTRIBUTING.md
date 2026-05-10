# Contributing to Civis

## When to open an issue first

Always for these:

- **Adding a new indicator.** Even one in an existing domain. Issue first;
  the discussion is whether the indicator belongs there at all, what its
  source and license are, and what its sign convention is. Code changes
  are easy after the question is settled.
- **Removing or renaming a domain.** Don't. Open an issue and wait for
  agreement before code.
- **Changing direction or scale of an existing indicator.** A direction flip
  changes every score; the validator will catch a flip but the design
  question deserves a discussion.
- **Changing the panel of countries.** The 29-country panel is intentional.
  Adding emerging economies changes the index's frame of reference.
- **Changing the aggregation method.** Mean → median, weighted → unweighted,
  per-year → panel-wide z, etc. These are baseline commitments that should
  not move without explicit agreement.

## When a PR is fine

- Code structure, refactoring, type hints, performance, lint cleanups.
- Bug fixes, including bugs in the methodology code that produce
  numerically wrong results. (If a fix changes scores, document the diff in
  the PR description and the CHANGELOG.)
- Documentation, README, METHOD additions and clarifications.
- New tests against existing methodology.
- Web app improvements that don't change the meaning of any chart.

## Branch and commit conventions

- Branch from `main`. Branch names: `feat/short-description`,
  `fix/short-description`, `data/short-description`,
  `docs/short-description`, `refactor/short-description`.
- Commit messages: imperative mood, present tense, lowercase prefix
  (`feat:`, `fix:`, `data:`, `docs:`, `refactor:`, `test:`, `ci:`).
- One concern per commit where reasonable.

## What "done" looks like

For methodology PRs, the PR description must include:

- A statement of what the change is and why.
- A before/after table of the latest-year top-10 ranking.
- A list of any indicators or domains affected.
- An update to `tests/fixtures/ranking_snapshot.json` if the ranking moved.
- Notes in `CHANGELOG.md` under the next version.

For non-methodology PRs:

- All tests pass (`pytest`, `ruff check`, `npm run typecheck`,
  `npm run build`).
- The bundle-size guard in CI is not breached.
- New code has a docstring or short comment explaining intent only when
  the *why* is non-obvious.

## Style

### Python

- `ruff` with the project config. Don't disable rules per file without
  saying why in a comment.
- Type-hint everything except trivial test functions.
- Module docstrings explain *why* the module exists.
- Avoid "could be cleaner" rewrites of working code in unrelated PRs.

### TypeScript

- `tsc --strict` clean. No `any` without a comment.
- One concern per file. The dashboard is small enough that splitting
  helpers further than `charts/` and `ui/` is premature.
- Don't introduce a state framework. The current `state.ts` (two
  highlights, nine weights, listener pattern) is sufficient and the
  dashboard is intentionally small.

### Visual identity

The dashboard is supposed to feel like an editorial-data-journalism artifact,
not a SaaS dashboard. Three concrete rules:

- **Don't change the colour palette.** `#1f2e26` background, `#94b09e`
  sage, `#d2965a` amber, `#d8dccd` ink. These are the project's identity.
- **Don't change the type stack.** Cormorant Garamond display, Newsreader
  body, JetBrains Mono meta. Refine, don't replace.
- **No em dashes in user-facing copy.** Periods or commas. (Project style
  preference — this codebase uses regular dashes intentionally.)

## Running things locally

See the bottom of [README.md](README.md). Short version:

```bash
uv venv --python 3.11 && uv pip install -e ".[dev]"
source .venv/bin/activate
pytest                 # unit tests
ruff check pipeline tests
civis fetch && civis process && civis validate

cd web
npm install
npm run dev            # http://localhost:5173
npm run build          # static output in web/dist
```

## Reporting issues

A good issue is one that someone reading it cold can act on. Please include:

- For bugs: how to reproduce; what you saw; what you expected; the
  validator output if any.
- For methodology proposals: the question, your suggestion, the
  trade-off, and one or more sources.
