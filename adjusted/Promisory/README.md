# Adjusted Promisory

Put all adjusted/generated Promisory `.per` modules in this directory.

Rules:

1. Preserve the official module filename when modifying an existing Promisory module.
2. Treat `official/raw/Promisory/` as read-only reference material.
3. Do not overwrite official source files with generated or experimental behavior.
4. Use this directory as the source for future game-test candidates after validation.
5. When possible, keep changes deterministic and traceable back to the decision block/compiler version that produced them.

Example mapping:

`official/raw/Promisory/tsa.per` → `adjusted/Promisory/tsa.per`

## Fixed Runtime v1

The fixed runtime source of truth is `adjusted/config/fixed-parameters.v1.json`.

Fixed modules currently materialized here:

- `const.per`
- `customConstants.per`
- `finalingConstants.per`
- `init.per`
- `dawn.per`
- `general.per`
- `finaling.per`
- `boarhunting.per`
- `resign.per`
- `interaction.per`
- `event.per`
- `events.per`
- `extremebuildings2.per`

Dynamic modules must not override the fixed values documented in `adjusted/PARAMETER_OWNERSHIP.md`.
