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

Batch 6 brings the current total to **17 templates and 2329 unique blanks**.

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

- `dawn.per` — 72 early gatherer-allocation timing/resource/count blanks;
- `finaling.per` — 16 late production population/resource/counter-trigger blanks;
- `resign.per` — 40 macro surrender population/time/superiority blanks.

- `merge1b.per` - 21 curated civilization building-target and Imperial gatherer-share blanks;
- `customConstants.per` - 432 blanks from the same seven-name allowlist, with duplicate WEI definitions and disabled zero-building targets kept fixed.

The remaining dynamic modules will be reviewed in small batches; a module may be kept fixed or skipped when its boundary is unclear. Until a module is migrated, its adjusted baseline remains the exact
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

### Batch 5 curation

- `dawn.per`: blanks are limited to time, villager/gatherer, sheep and gold thresholds inside rules that directly move villagers between food, wood, gold or stone. Increment/decrement actions, house logic and hard population-cap control remain fixed.
- `finaling.per`: blanks are limited to population/resource/unit-count thresholds inside direct `train` rules. Dock filter state, object IDs, existence checks and unrelated control flow remain fixed.
- `resign.per`: blanks are limited to macro population, enemy/ally population, time and military/team-superiority thresholds in rules that directly set `resign yes`. Zero/one survival checks, timer IDs and actual `resign` action remain fixed.


### Batch 6 curation

Only these exact `defconst` names are eligible in `merge1b.per` and
`customConstants.per`: `number-barracks`, `number-stables`,
`number-archery-ranges`, `ig-food`, `ig-wood`, `ig-gold`, and `ig-stone`.
The original integer value alone is replaced; names, civilization conditions,
comments, order and line endings remain byte-identical. Each occurrence has
its own answer and official default.

- Building constants are production-building targets; `ig-*` values feed the
  Imperial-age food/wood/gold/stone gatherer percentages.
- Both duplicate `WEI-CIV` blocks in `customConstants.per` stay fixed (14
  candidate values). They repeat the same symbols under the same condition;
  independently adjustable definitions could conflict.
- The Aztec and Mayan `number-stables 0` values stay fixed (2 values), preserving
  the original disabled target. No non-positive building target is exposed.
- The Saracen official `ig-*` values total 101. They are recorded unchanged;
  the migration does not normalize or repair the official source.
- `finalingConstants.per` is **fixed/skip** in this batch: its 24 candidates
  belong to difficulty-dependent idling, reaction, distance and escrow behavior.
- `uu-*`, `ur-*`, affinity values, sling settings, IDs, capability facts and
  unrelated definitions remain fixed. In particular, `ur-*` supplies research
  cost data rather than an independently verified strategy budget.

The dedicated guards bind every placeholder to an approved value span in the
original source. A placeholder in an ID, cost, comment, symbol name or an
additional expression is rejected even when official-default round trip would
succeed. The two Batch 6 modules cannot silently disappear from the checker.

See [Batch 6 review](BATCH6_REVIEW.md) for the source evidence and exclusions.
This proves static boundary preservation and exact restoration only; game
Parser/Load, Smoke, complete matches and strength remain **Unverified**.
