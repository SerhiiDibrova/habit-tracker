You are completing a development phase for the Habit Tracker MVP.

Read CLAUDE.md and specs/spec.MD to confirm which phase was just finished and what it required.

Run the following checks in order. Stop immediately if any check fails — do not proceed to the next check or declare the phase done.

## 1. Show changed files

List every file that was created or modified in this phase. Group by area: backend, frontend, config, tests.

## 2. Verify spec requirements

Cross-check the changed files against the spec requirements for this phase. Explicitly confirm each deliverable is present. If anything from the spec is missing, list it and stop.

## 3. Run backend checks (if backend files changed)

```bash
cd backend && source .venv/bin/activate && python -m py_compile $(git diff --name-only --diff-filter=ACM | grep '\.py$' | head -20) 2>&1
```

Then run tests if they exist:

```bash
cd backend && source .venv/bin/activate && pytest -q 2>&1
```

If pytest finds no tests yet, note that and continue. If tests exist and any fail, stop.

## 4. Run frontend checks (if frontend files changed)

```bash
cd frontend && npx tsc --noEmit 2>&1
```

If type errors exist, stop and fix them.

## 5. Report

Produce a short phase completion report:

- Phase number and name
- Files changed (count by area)
- Tests: pass / no tests yet / N failed
- Type check: pass / N errors
- Spec coverage: complete / missing items listed
- Verdict: DONE or BLOCKED (with reason)

Only output DONE if all checks passed and all spec deliverables for this phase are present.
