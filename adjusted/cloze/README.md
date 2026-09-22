# Official-derived PER Cloze

This is the strategy-authoring method.

Every template starts from the preserved official file under
`official/raw/Promisory/`.

We do not rewrite the rule structure. We only replace selected tunable values
with placeholders such as `{{TSA_MY_MILITARY_001}}`.

## Rule

- Text that is not a placeholder is fixed and remains official source.
- A placeholder is a value the strategy AI may fill.
- The AI receives one module template and its matching blank answer sheet.
- The renderer only substitutes answers into placeholders.
- If all placeholders are filled with their recorded official defaults, the
  result must be byte-for-byte identical to the official source file.

That last condition is enforced in CI.

## Current migration batch

Official-derived templates currently exist for:

- `gatherers.per` — 346 gatherer-percentage blanks;
- `tsa.per` — 348 military population/superiority threshold blanks;
- `orb.per` — 10 active attack-group blanks;
- `scoutcontrol.per` — 45 exploration count/time/tactical threshold blanks;
- `trade.per` — 266 market/resource/count threshold blanks;
- `escrow.per` — 448 age-up/research/economy/military threshold blanks.

The remaining dynamic modules will be migrated in the same way, three at a time. Until a module is migrated, its adjusted baseline remains the exact
official file.

Blank answer sheets live in `answers/`.
Recorded official values used for round-trip proof live in
`official-defaults/`.
