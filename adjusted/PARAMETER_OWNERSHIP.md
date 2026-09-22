# Parameter Ownership v1

This file defines who is allowed to choose each strategy/runtime field.

## Fixed — Runtime/Compiler owns it

| Current field / behavior | Fixed value |
|---|---:|
| Civilian exploration | disabled |
| Civilian explorer percent / cap / minimum | 0 / 0 / 0 |
| Initial land explore groups / explorers | 0 / 0 |
| Land/boat explore group min/max size | 1 / 1 |
| Civilian gatherer percent / cap | 100 / 1000 |
| Initial resource escrow | 0% on all four resources |
| Boar hunting initial state | disabled until activation rule |
| Boar hunting activation | 8 villagers |
| Maximum hunt drop distance | 12 |
| Attack intelligence | 1 |
| Attack separation randomness | 0 |
| Attack group-size randomness | 0 |
| Initial attack delay | 0 |
| Initial attack / defend groups | 0 / 0 |
| Baseline attack / defend group min/max | 1 / 1 |
| Patrol attack | enabled |
| Local targeting mode | 1 |
| Invalid target recovery | closest valid enemy |
| Human taunt strategy control | disabled |
| Automatic chat | disabled |
| Extreme building walling | disabled |
| Force old micro | disabled |
| Resignation | enabled |
| Faster resignation | disabled |
| Earliest terminal resignation check | 480 s |
| Terminal resignation timer | 5 s |
| Market exchange engine | enabled |
| Threat engine | enabled |
| Enemy building inside town counts as threat | yes |
| TSA attack-state engine | enabled |
| ORB attack-group engine | enabled |
| Idle fishing ship stops boat exploration | yes |

The strategy AI must not emit or override these values.

## Dynamic — Strategy AI owns it

These must remain variable because they depend on civilization, map, age, economy, enemy composition, or battle state:

- land and boat explorer counts;
- unit composition and ratios;
- military population targets;
- food / wood / gold / stone gatherer allocation;
- building counts and housing headroom;
- age-up escrow timing and percentages;
- market buy/sell stock, gold, and price thresholds;
- economic and military technology timing;
- threat unit-count trigger/clear thresholds;
- attack start/stop military thresholds;
- attack group size;
- percentage of military committed to attack;
- target priority and strategic target selection.

## Current decision-schema cleanup

Fields that should be removed from future LLM decision blocks because they are fixed:

- `scoutcontrol.enabled`
- `scoutcontrol.civilian_exploration`
- `boarhunting.enabled`
- `boarhunting.start_villager_count`
- `boarhunting.maximum_hunt_drop_distance`
- `trade.enabled`
- `watercontrol.enabled`
- `watercontrol.idle_fishing_ship_stops_exploration`
- `resign.enabled`
- `resign.minimum_game_time`
- `threats.enabled`
- `threats.enemy_buildings_in_town_trigger`
- `tsa.enabled`
- `orb.enabled`

The remaining dynamic fields are now represented by `adjusted/schema/dynamic-strategy.v1.schema.json` as age-scoped base plans plus typed, priority-ordered reactions.
