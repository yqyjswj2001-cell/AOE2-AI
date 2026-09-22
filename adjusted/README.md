# Adjusted AI Scripts

This directory contains project-authored or project-adjusted Age of Empires II AI scripts.

## Boundary

- `official/` remains the preserved reference/archive and must not be edited for project changes.
- `adjusted/` contains our working derivatives, generated scripts, and runtime experiments.
- Adjusted Promisory modules live under `adjusted/Promisory/`.
- Keep adjusted module filenames aligned with the corresponding official files under `official/raw/Promisory/` whenever a direct counterpart exists.

This separation is intentional so official source, generated output, diffs, rollback, and in-game test candidates remain distinguishable.

## Parameter ownership

- `config/fixed-parameters.v1.json` — authoritative fixed runtime values.
- `PARAMETER_OWNERSHIP.md` — fixed vs dynamic ownership contract.
- Strategy-generation models must only choose fields classified as dynamic.

## Dynamic strategy — PER cloze

Dynamic strategy is authored through `cloze/Promisory/*.per.tpl`.

- The PER rule structure is fixed.
- The AI fills only the matching JSON blanks under `cloze/answers/`, one module at a time.
- `tools/render_per_cloze.py` performs mechanical substitution and validation.
- No natural-language interpretation or AI-authored PER rule structure is part of the execution path.

See `cloze/README.md`.
