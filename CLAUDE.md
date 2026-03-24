# Development Protocol

## Prime Directives

1. Verify everything. Check official docs before coding. Query current date first.
2. Never hardcode. Generalize all solutions, even for "quick tests".
3. Never manually copy. Everything must be programmatically coherent.
4. Never modify tests to pass. Fix root causes only.
5. Own your changes. Fix flaky tests and regressions you cause.
6. No bypassing. Never twist configs or tests to fake success.
7. Simplest approach. Never overcomplicate or add unnecessary comments.

## Stack

- Language: Python 3.11+
- GUI: PySide6
- PDF backend: PyMuPDF (fitz), pypdf, pdfplumber
- Packaging: PyInstaller (Windows .exe via Inno Setup, macOS .app)

## Tool Hierarchy

- Default: use built-in tools and sub-agents first.
- Skills: use available skills (frontend-design, simplify, commit, etc.) before reinventing.
- Last resort: generic bash or regex only when the above cannot do the job.

## Code Standards

- Plain style. No bold, emojis, decorative comments, or editorializing.
- Conventional Commits: feat, fix, docs, refactor, test, chore.
- Atomic commits. Include tests and implementation in the same commit.
- No Co-Authored-By lines or watermarks in commits.
- No docstrings or type annotations added to code you did not change.

## Secrets and Environment Variables

- Never hardcode secrets, API keys, file paths, or user-specific values.
- Never commit `.env` files. They must be listed in `.gitignore`.
- Read secrets at runtime via `os.environ.get(...)` or a `.env` loader (e.g. `python-dotenv`).
- If a secret is missing at runtime, raise a clear error — do not silently fall back to a default.
- Never log or print secret values, even in debug output.
- If you touch code that handles paths (PDF files, output dirs), make them configurable — never assume a specific user directory.

## Testing Strategy

- Baseline first: run all tests before implementing. Fix any existing failures.
- Unit tests for: specific input/output pairs, edge cases, error paths.
- No skipped tests: detect and re-enable skipped tests, investigate root causes.
- Tests live in `tests/`. Run with `pytest`.

## Project State

Before adding any new feature or making structural changes, read `docs/project-state/` first:
- `docs/project-state/ARCHITECTURE.md` — how modules relate, data flow, shared components.
- `docs/project-state/FEATURES.md` — catalog of every implemented feature.

When a new feature is added, append it to `FEATURES.md` under the relevant module section using the same format (feature name, description, module/method, dependencies). Add a corresponding entry to `docs/CHANGELOG.md`.

## Documentation Index

| Doc | When to read |
|---|---|
| `docs/project-state/ARCHITECTURE.md` | Before any structural or cross-module change |
| `docs/project-state/FEATURES.md` | Before adding a feature (check it doesn't exist) |
| `docs/CHANGELOG.md` | When committing — add an entry for every change |
| `docs/CONVENTIONS.md` | Before writing any new code — naming, imports, patterns |
| `docs/DATABASE.md` | Before touching `LibraryState` or `library.json` |
| `docs/API.md` | Before changing public interfaces of any module |
| `docs/TESTING.md` | Before writing or running tests |
| `docs/ENV.md` | For setup, env vars, and build instructions |
| `docs/TROUBLESHOOTING.md` | When hitting a known issue; add new ones here |
| `docs/PR_STANDARDS.md` | Before opening or reviewing a PR |
| `docs/DESIGN_STANDARDS.md` | Before touching any UI code |

## Workflow

### Before Coding
1. Check current date for temporal context.
2. Read `docs/project-state/ARCHITECTURE.md` and `FEATURES.md` to understand current structure.
3. Explore codebase structure and existing patterns.
4. Verify current library syntax — do not rely on training data for PyMuPDF or PySide6 APIs.
5. Define: Goal, Acceptance Criteria, Definition of Done, Non-goals.

### Trivial Edits Exception
For typos or one-line non-logic changes: skip requirements, run linter, commit.

### Verification Chain
Run in order, committing at each green step:
1. Feature-specific tests
2. `ruff format` (formatter)
3. `ruff check` (linter)
4. Full test suite via `pytest`

### When Stuck
Write one-off programs in `./playground/` to isolate and test intent or hypothesis.

## Pull Requests

When opening, reviewing, or merging a PR, read and apply `docs/PR_STANDARDS.md` in full before proceeding.

## Design

When adding or changing any UI — layouts, colors, icons, spacing, components — read and apply `docs/DESIGN_STANDARDS.md` in full before proceeding.

## Python Pitfalls

- Never use mutable default arguments (`def f(x=[])`).
- Never catch bare `except:` — always catch specific exception types.
- PySide6 UI must only be modified from the main thread. Use signals/slots for cross-thread updates.
- PyMuPDF objects (`fitz.Document`, `fitz.Page`) must be explicitly closed — use context managers or `__del__`.
- Do not block the Qt event loop. Use `QThread` or `QRunnable` for PDF rendering and IO.
- When packaging with PyInstaller, verify that binary dependencies (MuPDF) are bundled — check the spec file.
