# Batch 6 static review

Source repository: `yqyjswj2001-cell/AOE2-AI`.
Frozen source commit: `4af2025103919102b3d64792a33a2c66f951fefa`.

| Module | Decision | Blanks |
| --- | --- | ---: |
| `merge1b.per` | Seven exact building-target / Imperial gatherer-share names | 21 |
| `customConstants.per` | Same seven names; exclude duplicate WEI blocks and zero building targets | 432 |
| `finalingConstants.per` | Keep difficulty-dependent values fixed | 0 |

Batch total: 453 new blanks; repository total: 17 templates / 2329 blanks.

## Direct source evidence

All paths below are under the frozen `official/raw/Promisory/` tree.

- `buildings.per`, lines 9007-9042: `number-barracks`, `number-stables` and
  `number-archery-ranges` feed the corresponding production-building targets.
- `gatherers.per`, lines 1143-1152 and 1191-1203: `ig-food`, `ig-wood`, `ig-gold`
  and `ig-stone` feed Imperial-age resource gatherer percentages.
- `merge1b.per`: three civilization branches, with building targets at
  31-33 / 90-92 / 150-152 and gatherer shares at 44-47 / 103-106 / 163-166.
- `customConstants.per`: 64 configuration blocks under 63 distinct CIV
  conditions contain the seven names. Both `WEI-CIV` blocks beginning at
  5558 and 5614 remain fixed, excluding 14 candidate values. Aztec and Mayan
  stable targets at 2725 and 4156 remain fixed at zero, excluding two more.
- Saracen gatherer shares at `customConstants.per:4473-4476` total 101 in the
  source. Their recorded defaults are preserved exactly, not normalized.

## Deliberate exclusions

`finalingConstants.per` lines 6-53 repeat idling, reaction percentage, reaction
distance and escrow constants in six difficulty branches, alongside jump and
initial-delay controls. `finaling.per:1-18` applies those settings. This batch
keeps all 24 candidates fixed rather than exposing difficulty and response
mechanisms as independently tunable strategy.

`escrow.per:994-1016` uses the engine research-cost query for older civilizations
and `ur-*` for the newer-civilization cost fallback. Those are cost facts.
`uu-*` and affinity families have not received a complete per-symbol use audit;
`init.per:8371` even uses `castledrop-affinity` in a goal argument position.
They and all other unlisted symbols, IDs, feature flags, search distances,
control flow, comments and preprocessor structure remain fixed.

## Verification boundary

Required checks are `python -B adjusted/tools/check_official_cloze.py` and
`python -B -m unittest discover -s adjusted/tests -v`. The checker verifies the
36 untouched baselines, original source blob hashes, exact default restoration,
blank answer sheets, and the two new module guards. Tests also exercise attacks
that preserve round trip but move blanks into fixed positions.

These are static proofs. No game was installed, started or controlled.
Parser/Load, Smoke, complete matches and strength are `Unverified`.
