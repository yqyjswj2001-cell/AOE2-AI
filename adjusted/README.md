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

## Dynamic strategy

- `schema/dynamic-strategy.v1.schema.json` — the bounded contract the strategy AI may author.
- `DYNAMIC_STRATEGY.md` — base-plan, reaction, and deterministic priority semantics.
- `examples/franks.dynamic-strategy.v1.json` — example strategy payload.
- `tools/check_dynamic_strategy.py` — cross-field and fixed-field leakage checks.

Dynamic strategy contains no raw PER, Goal IDs, Strategic Numbers, timers, jumps, or fixed runtime switches.
