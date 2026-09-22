; CLOZE TEMPLATE - rule structure is fixed
(defrule
    (true)
=>
    (enable-timer fifteensec 15)
    (disable-self)
)

(defrule
    (current-age == dark-age)
=>
    (set-strategic-number sn-number-explore-groups {{DARK_LAND_EXPLORERS}})
    (set-strategic-number sn-total-number-explorers {{DARK_LAND_EXPLORERS}})
    (set-strategic-number sn-number-boat-explore-groups {{DARK_BOAT_EXPLORERS}})
)
(defrule
    (current-age == feudal-age)
=>
    (set-strategic-number sn-number-explore-groups {{FEUDAL_LAND_EXPLORERS}})
    (set-strategic-number sn-total-number-explorers {{FEUDAL_LAND_EXPLORERS}})
    (set-strategic-number sn-number-boat-explore-groups {{FEUDAL_BOAT_EXPLORERS}})
)
(defrule
    (current-age == castle-age)
=>
    (set-strategic-number sn-number-explore-groups {{CASTLE_LAND_EXPLORERS}})
    (set-strategic-number sn-total-number-explorers {{CASTLE_LAND_EXPLORERS}})
    (set-strategic-number sn-number-boat-explore-groups {{CASTLE_BOAT_EXPLORERS}})
)
(defrule
    (current-age == imperial-age)
=>
    (set-strategic-number sn-number-explore-groups {{IMPERIAL_LAND_EXPLORERS}})
    (set-strategic-number sn-total-number-explorers {{IMPERIAL_LAND_EXPLORERS}})
    (set-strategic-number sn-number-boat-explore-groups {{IMPERIAL_BOAT_EXPLORERS}})
)
(defrule
    (timer-triggered fifteensec)
    (strategic-number sn-number-explore-groups > 0)
    (military-population >= 1)
=>
    (up-send-scout group-type-land-explore scout-center)
    (enable-timer fifteensec 15)
)
(defrule
    (timer-triggered fifteensec)
=>
    (enable-timer fifteensec 15)
)
