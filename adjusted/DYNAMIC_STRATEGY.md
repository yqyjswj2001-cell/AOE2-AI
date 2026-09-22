# Dynamic Strategy v1

Dynamic Strategy v1 is the only layer the strategy AI is allowed to author.

It deliberately excludes runtime safety switches and fixed parameters from
`adjusted/config/fixed-parameters.v1.json`.

## Structure

A strategy has two layers:

1. **base_plan** — the normal plan for each age.
2. **reactions** — bounded contingency plans selected from typed triggers.

The AI never writes PER expressions, Goal IDs, Strategic Numbers, timers, jumps,
or fixed runtime switches.

## Base plan domains

The base plan controls:

- scouting unit counts;
- four-resource economy allocation;
- military composition and target military population;
- building counts and housing headroom;
- Feudal/Castle/Imperial age-up escrow;
- market buy/sell thresholds;
- economic and military research timing;
- threat trigger/clear counts;
- attack start/stop population, attack group size, and committed-soldier percent;
- strategic target priority.

Every age has an explicit plan. Dark Age may use a zero military/combat plan.

## Reaction model

v1 allows only these trigger families:

- `enemy_unit_pressure`
- `resource_shortage`
- `under_attack`
- `military_disadvantage`
- `enemy_fortification`

A reaction may override only these domains:

- scouting;
- economy;
- military;
- combat;
- target priority.

No arbitrary condition/action strings are allowed.

## Deterministic reaction resolution

At runtime:

1. Select the current-age values from `base_plan`.
2. Evaluate reactions whose `ages` include the current age.
3. Keep only reactions whose typed trigger is true.
4. Sort active reactions by `priority`, highest first.
5. Resolve each override domain independently: the highest-priority active
   reaction that supplies that domain wins.
6. Domains not overridden keep their base-plan values.

Reaction priorities must therefore be unique in v1. This avoids ambiguous
compound behavior and makes the generated PER reproducible.

Example: if an under-attack reaction with priority 100 overrides combat, and a
gold-shortage reaction with priority 70 overrides economy, both can be active:
combat comes from the first reaction and economy from the second.

## Ownership boundary

The following are intentionally **not** dynamic-strategy fields:

- feature enable/disable switches;
- civilian exploration policy;
- boar activation and hunt-distance safety;
- resign enable/timing;
- automatic chat/taunt behavior;
- extreme building walling;
- attack-engine implementation switches;
- fixed Goal/Timer/SN/constant values.

Those are owned by Fixed Runtime v1.

## Next compiler step

The compiler should consume this schema and generate only the strategy-owned
parts of the matching Promisory modules. It must never overwrite fixed-runtime
values.
