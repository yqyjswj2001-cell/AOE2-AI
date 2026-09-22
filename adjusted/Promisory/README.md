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
