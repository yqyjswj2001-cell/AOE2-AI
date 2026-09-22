; CLOZE TEMPLATE - AI fills unit symbols, caps, and total military target
; DARK
(defrule
    (current-age == dark-age)
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_1}} < {{DARK_UNIT_1_CAP}})
    (can-train {{DARK_UNIT_1}})
=>
    (train {{DARK_UNIT_1}})
)
(defrule
    (current-age == dark-age)
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_2}} < {{DARK_UNIT_2_CAP}})
    (can-train {{DARK_UNIT_2}})
=>
    (train {{DARK_UNIT_2}})
)
(defrule
    (current-age == dark-age)
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_3}} < {{DARK_UNIT_3_CAP}})
    (can-train {{DARK_UNIT_3}})
=>
    (train {{DARK_UNIT_3}})
)

; FEUDAL
(defrule
    (current-age == feudal-age)
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_1}} < {{FEUDAL_UNIT_1_CAP}})
    (can-train {{FEUDAL_UNIT_1}})
=>
    (train {{FEUDAL_UNIT_1}})
)
(defrule
    (current-age == feudal-age)
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_2}} < {{FEUDAL_UNIT_2_CAP}})
    (can-train {{FEUDAL_UNIT_2}})
=>
    (train {{FEUDAL_UNIT_2}})
)
(defrule
    (current-age == feudal-age)
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_3}} < {{FEUDAL_UNIT_3_CAP}})
    (can-train {{FEUDAL_UNIT_3}})
=>
    (train {{FEUDAL_UNIT_3}})
)

; CASTLE
(defrule
    (current-age == castle-age)
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_1}} < {{CASTLE_UNIT_1_CAP}})
    (can-train {{CASTLE_UNIT_1}})
=>
    (train {{CASTLE_UNIT_1}})
)
(defrule
    (current-age == castle-age)
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_2}} < {{CASTLE_UNIT_2_CAP}})
    (can-train {{CASTLE_UNIT_2}})
=>
    (train {{CASTLE_UNIT_2}})
)
(defrule
    (current-age == castle-age)
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_3}} < {{CASTLE_UNIT_3_CAP}})
    (can-train {{CASTLE_UNIT_3}})
=>
    (train {{CASTLE_UNIT_3}})
)

; IMPERIAL
(defrule
    (current-age == imperial-age)
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_1}} < {{IMPERIAL_UNIT_1_CAP}})
    (can-train {{IMPERIAL_UNIT_1}})
=>
    (train {{IMPERIAL_UNIT_1}})
)
(defrule
    (current-age == imperial-age)
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_2}} < {{IMPERIAL_UNIT_2_CAP}})
    (can-train {{IMPERIAL_UNIT_2}})
=>
    (train {{IMPERIAL_UNIT_2}})
)
(defrule
    (current-age == imperial-age)
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_3}} < {{IMPERIAL_UNIT_3_CAP}})
    (can-train {{IMPERIAL_UNIT_3}})
=>
    (train {{IMPERIAL_UNIT_3}})
)

