# Adjusted AI Scripts

- `official/raw/Promisory/` is the preserved official reference.
- `adjusted/Promisory/` is a byte-identical working baseline of all 36 official
  Promisory `.per` files.
- `adjusted/cloze/Promisory/` contains official-derived templates where only
  selected dynamic values are replaced by placeholders.
- `adjusted/cloze/answers/` is what the strategy AI fills, one module at a time.

No separate rewritten runtime or abstract strategy language is used.

See `PARAMETER_OWNERSHIP.md` and `cloze/README.md`.
