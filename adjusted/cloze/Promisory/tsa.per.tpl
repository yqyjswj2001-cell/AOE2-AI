; CLOZE TEMPLATE - fixed combat priority: under attack stops attack; military disadvantage > base
(defrule
    (current-age == dark-age)
    (goal underattack no)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{DISADV_DARK_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == dark-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{DISADV_DARK_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == dark-age)
    (goal underattack no)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{DARK_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == dark-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{DARK_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == feudal-age)
    (goal underattack no)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{DISADV_FEUDAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == feudal-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{DISADV_FEUDAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == feudal-age)
    (goal underattack no)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{FEUDAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == feudal-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{FEUDAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == castle-age)
    (goal underattack no)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{DISADV_CASTLE_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == castle-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{DISADV_CASTLE_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == castle-age)
    (goal underattack no)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{CASTLE_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == castle-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{CASTLE_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == imperial-age)
    (goal underattack no)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{DISADV_IMPERIAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == imperial-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{DISADV_IMPERIAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
(defrule
    (current-age == imperial-age)
    (goal underattack no)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking no)
    (military-population >= {{IMPERIAL_ATTACK_START}})
    (players-building-count any-enemy >= 1)
=>
    (set-goal attacking yes)
)
(defrule
    (current-age == imperial-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
(or (military-population <= {{IMPERIAL_ATTACK_STOP}})
    (goal underattack yes))
=>
    (set-goal attacking no)
)
