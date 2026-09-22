; CLOZE TEMPLATE - AI fills only resource percentages
(defrule
    (current-age == dark-age)
=>
    (set-strategic-number sn-food-gatherer-percentage {{DARK_FOOD}})
    (set-strategic-number sn-wood-gatherer-percentage {{DARK_WOOD}})
    (set-strategic-number sn-gold-gatherer-percentage {{DARK_GOLD}})
    (set-strategic-number sn-stone-gatherer-percentage {{DARK_STONE}})
)
(defrule
    (current-age == feudal-age)
=>
    (set-strategic-number sn-food-gatherer-percentage {{FEUDAL_FOOD}})
    (set-strategic-number sn-wood-gatherer-percentage {{FEUDAL_WOOD}})
    (set-strategic-number sn-gold-gatherer-percentage {{FEUDAL_GOLD}})
    (set-strategic-number sn-stone-gatherer-percentage {{FEUDAL_STONE}})
)
(defrule
    (current-age == castle-age)
=>
    (set-strategic-number sn-food-gatherer-percentage {{CASTLE_FOOD}})
    (set-strategic-number sn-wood-gatherer-percentage {{CASTLE_WOOD}})
    (set-strategic-number sn-gold-gatherer-percentage {{CASTLE_GOLD}})
    (set-strategic-number sn-stone-gatherer-percentage {{CASTLE_STONE}})
)
(defrule
    (current-age == imperial-age)
=>
    (set-strategic-number sn-food-gatherer-percentage {{IMPERIAL_FOOD}})
    (set-strategic-number sn-wood-gatherer-percentage {{IMPERIAL_WOOD}})
    (set-strategic-number sn-gold-gatherer-percentage {{IMPERIAL_GOLD}})
    (set-strategic-number sn-stone-gatherer-percentage {{IMPERIAL_STONE}})
)
