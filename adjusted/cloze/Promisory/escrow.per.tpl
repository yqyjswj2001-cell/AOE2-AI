; CLOZE TEMPLATE - age-up escrow rule structure is fixed
(defrule
    (current-age == dark-age)
    (civilian-population >= {{FEUDAL_AGEUP_POP}})
    (not (can-research-with-escrow feudal-age))
=>
    (set-escrow-percentage food {{FEUDAL_AGEUP_FOOD_PCT}})
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold {{FEUDAL_AGEUP_GOLD_PCT}})
    (set-escrow-percentage stone 0)
)
(defrule
    (current-age == dark-age)
    (civilian-population >= {{FEUDAL_AGEUP_POP}})
    (can-research-with-escrow feudal-age)
=>
    (research feudal-age)
    (set-escrow-percentage food 0)
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold 0)
    (set-escrow-percentage stone 0)
)
(defrule
    (current-age == feudal-age)
    (civilian-population >= {{CASTLE_AGEUP_POP}})
    (not (can-research-with-escrow castle-age))
=>
    (set-escrow-percentage food {{CASTLE_AGEUP_FOOD_PCT}})
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold {{CASTLE_AGEUP_GOLD_PCT}})
    (set-escrow-percentage stone 0)
)
(defrule
    (current-age == feudal-age)
    (civilian-population >= {{CASTLE_AGEUP_POP}})
    (can-research-with-escrow castle-age)
=>
    (research castle-age)
    (set-escrow-percentage food 0)
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold 0)
    (set-escrow-percentage stone 0)
)
(defrule
    (current-age == castle-age)
    (civilian-population >= {{IMPERIAL_AGEUP_POP}})
    (not (can-research-with-escrow imperial-age))
=>
    (set-escrow-percentage food {{IMPERIAL_AGEUP_FOOD_PCT}})
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold {{IMPERIAL_AGEUP_GOLD_PCT}})
    (set-escrow-percentage stone 0)
)
(defrule
    (current-age == castle-age)
    (civilian-population >= {{IMPERIAL_AGEUP_POP}})
    (can-research-with-escrow imperial-age)
=>
    (research imperial-age)
    (set-escrow-percentage food 0)
    (set-escrow-percentage wood 0)
    (set-escrow-percentage gold 0)
    (set-escrow-percentage stone 0)
)
