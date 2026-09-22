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
- `tsa.per` — 157 military population/superiority blanks, restricted to rules that directly switch `attacking yes/no`;
- `orb.per` — 10 active attack-group blanks;
- `scoutcontrol.per` — 45 exploration count/time/tactical threshold blanks;
- `trade.per` — 266 market/resource/count threshold blanks;
- `escrow.per` — 448 age-up/research/economy/military threshold blanks.

- `units.per` — 27 same-unit production-cap blanks;
- `buildings.per` — 80 same-building target-count blanks;
- `researches.per` — 297 trigger blanks limited to common economy technologies and common military upgrades.

- `boarhunting.per` — 56 boar timing, villager and food/sheep trigger blanks;
- `threats.per` — 6 direct enemy military-population target-switch blanks;
- `watercontrol.per` — 10 naval attack/retreat water-advantage blanks.

The remaining dynamic modules will be migrated in the same way, three at a time. Until a module is migrated, its adjusted baseline remains the exact
official file.

Blank answer sheets live in `answers/`.
Recorded official values used for round-trip proof live in
`official-defaults/`.

## Curation rule

A numeric literal is not automatically a strategy parameter.

- `gatherers.per`: only direct food/wood/gold/stone gatherer-percentage assignments are exposed.
- `tsa.per`: only thresholds inside rules that directly switch the `attacking` state are exposed.
- `orb.per`: only attack-group Strategic Number values are exposed.
- Goal IDs, timer IDs, jump counts, flags, object IDs, recovery constants, micro-control thresholds, and unrelated implementation values stay official and fixed.

This policy is enforced by CI in addition to the byte-for-byte official-default round-trip check.

### Batch 3 curation

- `units.per`: a blank is allowed only when a direct `train X` rule compares the current count of that same `X`.
- `buildings.per`: a blank is allowed only when a direct `build X` rule compares the current count of that same `X`.
- `researches.per`: economic-tech blanks are limited to positive economy/population timing thresholds; military-tech blanks are limited to positive own-army beneficiary thresholds. Technology names and civilization-specific research branches remain official and fixed.

### Batch 4 curation

- `boarhunting.per`: blanks are limited to time, villager, sheep/food thresholds in rules that directly compute `minBoar` or enable boar hunting. Hunting distances, IDs and micro-control values stay fixed.
- `threats.per`: blanks are limited to the enemy military-population thresholds in the direct rule that switches both target and focus player. Player IDs, timers, search radii and arithmetic weights stay fixed.
- `watercontrol.per`: blanks are limited to `water-advantage` comparisons in rules that choose a water action. Formation, range, distance, object filters and action IDs stay fixed.
