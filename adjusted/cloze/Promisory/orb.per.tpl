; CLOZE TEMPLATE - group actuator; military disadvantage > base
(defrule
    (current-age == dark-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{DISADV_DARK_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{DISADV_DARK_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{DISADV_DARK_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == dark-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{DARK_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{DARK_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{DARK_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == feudal-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{DISADV_FEUDAL_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{DISADV_FEUDAL_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{DISADV_FEUDAL_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == feudal-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{FEUDAL_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{FEUDAL_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{FEUDAL_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == castle-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{DISADV_CASTLE_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{DISADV_CASTLE_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{DISADV_CASTLE_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == castle-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{CASTLE_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{CASTLE_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{CASTLE_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == imperial-age)
    (strategic-number sn-military-superiority <= -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{DISADV_IMPERIAL_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{DISADV_IMPERIAL_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{DISADV_IMPERIAL_ATTACK_GROUP_SIZE}})
)
(defrule
    (current-age == imperial-age)
    (strategic-number sn-military-superiority > -{{MILITARY_DISADVANTAGE}})
    (goal attacking yes)
=>
    (set-strategic-number sn-number-attack-groups 1000)
    (set-strategic-number sn-percent-attack-soldiers {{IMPERIAL_ATTACK_PERCENT}})
    (set-strategic-number sn-minimum-attack-group-size {{IMPERIAL_ATTACK_GROUP_SIZE}})
    (set-strategic-number sn-maximum-attack-group-size {{IMPERIAL_ATTACK_GROUP_SIZE}})
)
(defrule
    (goal attacking no)
=>
    (set-strategic-number sn-number-attack-groups 0)
    (set-strategic-number sn-percent-attack-soldiers 0)
    (set-strategic-number sn-minimum-attack-group-size 1)
    (set-strategic-number sn-maximum-attack-group-size 1)
)
