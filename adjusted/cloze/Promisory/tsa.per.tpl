; CLOZE TEMPLATE - attack-state rules are fixed
(defrule
    (current-age == dark-age)
    (goal underattack no)
    (goal attacking no)
    (military-population >= {{DARK_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == dark-age)
    (goal attacking yes)
(or (military-population <= {{DARK_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == feudal-age)
    (goal underattack no)
    (goal attacking no)
    (military-population >= {{FEUDAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == feudal-age)
    (goal attacking yes)
(or (military-population <= {{FEUDAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == castle-age)
    (goal underattack no)
    (goal attacking no)
    (military-population >= {{CASTLE_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == castle-age)
    (goal attacking yes)
(or (military-population <= {{CASTLE_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == imperial-age)
    (goal underattack no)
    (goal attacking no)
    (military-population >= {{IMPERIAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == imperial-age)
    (goal attacking yes)
(or (military-population <= {{IMPERIAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
