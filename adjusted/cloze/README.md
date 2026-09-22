# PER Cloze v1

This is the dynamic authoring surface.

The rule structure is already written in `Promisory/*.per.tpl`. Dynamic values
are replaced by placeholders such as `{{CASTLE_ATTACK_GROUP_SIZE}}`.

The strategy AI does **not** write PER rules. It only fills the JSON answer
sheet that belongs to the current module.

## Workflow

1. Give the AI one template, for example `Promisory/tsa.per.tpl`.
2. Give it only the matching answer sheet, for example `answers/tsa.json`,
   plus `answers/shared.json` if that module uses shared blanks.
3. The AI replaces only the null values in the answer sheet.
4. `render_per_cloze.py` mechanically substitutes the answers into the fixed
   template.
5. Validation rejects missing blanks, unknown blanks, unsafe symbols, invalid
   percentages, inverted thresholds, and unbalanced PER.

There is no natural-language-to-parameter conversion and no AI-authored rule
structure.

## Fixed reaction slots

The reaction rule shapes are also fixed.

- economy: one resource-shortage slot;
- military production: enemy-unit-pressure first, enemy-fortification second,
  then the base plan;
- combat: under-attack always stops the normal attack state;
- combat: military-disadvantage values override normal attack thresholds and
  group settings.

The AI fills the resource/unit/building symbols, counts, and replacement values.
It does not create new reaction syntax.

## Render

For the repository test fixture:

```sh
python3 -B adjusted/tools/render_per_cloze.py \
  --answers-dir adjusted/tests/fixtures/cloze-franks \
  --out /tmp/aoe2-cloze
```

The normal authoring flow uses the blank files under `answers/`, one module at
a time.
