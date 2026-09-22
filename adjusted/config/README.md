# Fixed Runtime Configuration

`fixed-parameters.v1.json` is the authoritative source for values the strategy AI is not allowed to choose.

The rule is strict:

- If a value can reasonably change because of civilization, map, enemy composition, economy, age, or battle state, it is **not fixed**.
- Fixed values are runtime safety/infrastructure choices only.
- Player-facing preferences may later be separated into their own settings file; they must still not be inferred by the strategy AI.
- Dynamic strategy belongs in a separate decision layer.

The adjusted `.per` files should agree with this file. If a fixed value changes, change the configuration and the consuming runtime together.
