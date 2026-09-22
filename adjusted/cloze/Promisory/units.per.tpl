; CLOZE TEMPLATE - fixed reaction priority: unit pressure > fortification > base
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_DARK_UNIT_1}} < {{PRESSURE_DARK_UNIT_1_CAP}})
    (can-train {{PRESSURE_DARK_UNIT_1}})
=>
    (train {{PRESSURE_DARK_UNIT_1}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_DARK_UNIT_2}} < {{PRESSURE_DARK_UNIT_2_CAP}})
    (can-train {{PRESSURE_DARK_UNIT_2}})
=>
    (train {{PRESSURE_DARK_UNIT_2}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_DARK_UNIT_3}} < {{PRESSURE_DARK_UNIT_3_CAP}})
    (can-train {{PRESSURE_DARK_UNIT_3}})
=>
    (train {{PRESSURE_DARK_UNIT_3}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_DARK_UNIT_1}} < {{FORT_DARK_UNIT_1_CAP}})
    (can-train {{FORT_DARK_UNIT_1}})
=>
    (train {{FORT_DARK_UNIT_1}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_DARK_UNIT_2}} < {{FORT_DARK_UNIT_2_CAP}})
    (can-train {{FORT_DARK_UNIT_2}})
=>
    (train {{FORT_DARK_UNIT_2}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_DARK_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_DARK_UNIT_3}} < {{FORT_DARK_UNIT_3_CAP}})
    (can-train {{FORT_DARK_UNIT_3}})
=>
    (train {{FORT_DARK_UNIT_3}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_1}} < {{DARK_UNIT_1_CAP}})
    (can-train {{DARK_UNIT_1}})
=>
    (train {{DARK_UNIT_1}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_2}} < {{DARK_UNIT_2_CAP}})
    (can-train {{DARK_UNIT_2}})
=>
    (train {{DARK_UNIT_2}})
)
(defrule
    (current-age == dark-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{DARK_MILITARY_TARGET}})
    (unit-type-count-total {{DARK_UNIT_3}} < {{DARK_UNIT_3_CAP}})
    (can-train {{DARK_UNIT_3}})
=>
    (train {{DARK_UNIT_3}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_FEUDAL_UNIT_1}} < {{PRESSURE_FEUDAL_UNIT_1_CAP}})
    (can-train {{PRESSURE_FEUDAL_UNIT_1}})
=>
    (train {{PRESSURE_FEUDAL_UNIT_1}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_FEUDAL_UNIT_2}} < {{PRESSURE_FEUDAL_UNIT_2_CAP}})
    (can-train {{PRESSURE_FEUDAL_UNIT_2}})
=>
    (train {{PRESSURE_FEUDAL_UNIT_2}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_FEUDAL_UNIT_3}} < {{PRESSURE_FEUDAL_UNIT_3_CAP}})
    (can-train {{PRESSURE_FEUDAL_UNIT_3}})
=>
    (train {{PRESSURE_FEUDAL_UNIT_3}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_FEUDAL_UNIT_1}} < {{FORT_FEUDAL_UNIT_1_CAP}})
    (can-train {{FORT_FEUDAL_UNIT_1}})
=>
    (train {{FORT_FEUDAL_UNIT_1}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_FEUDAL_UNIT_2}} < {{FORT_FEUDAL_UNIT_2_CAP}})
    (can-train {{FORT_FEUDAL_UNIT_2}})
=>
    (train {{FORT_FEUDAL_UNIT_2}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_FEUDAL_UNIT_3}} < {{FORT_FEUDAL_UNIT_3_CAP}})
    (can-train {{FORT_FEUDAL_UNIT_3}})
=>
    (train {{FORT_FEUDAL_UNIT_3}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_1}} < {{FEUDAL_UNIT_1_CAP}})
    (can-train {{FEUDAL_UNIT_1}})
=>
    (train {{FEUDAL_UNIT_1}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_2}} < {{FEUDAL_UNIT_2_CAP}})
    (can-train {{FEUDAL_UNIT_2}})
=>
    (train {{FEUDAL_UNIT_2}})
)
(defrule
    (current-age == feudal-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{FEUDAL_MILITARY_TARGET}})
    (unit-type-count-total {{FEUDAL_UNIT_3}} < {{FEUDAL_UNIT_3_CAP}})
    (can-train {{FEUDAL_UNIT_3}})
=>
    (train {{FEUDAL_UNIT_3}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_CASTLE_UNIT_1}} < {{PRESSURE_CASTLE_UNIT_1_CAP}})
    (can-train {{PRESSURE_CASTLE_UNIT_1}})
=>
    (train {{PRESSURE_CASTLE_UNIT_1}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_CASTLE_UNIT_2}} < {{PRESSURE_CASTLE_UNIT_2_CAP}})
    (can-train {{PRESSURE_CASTLE_UNIT_2}})
=>
    (train {{PRESSURE_CASTLE_UNIT_2}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_CASTLE_UNIT_3}} < {{PRESSURE_CASTLE_UNIT_3_CAP}})
    (can-train {{PRESSURE_CASTLE_UNIT_3}})
=>
    (train {{PRESSURE_CASTLE_UNIT_3}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_CASTLE_UNIT_1}} < {{FORT_CASTLE_UNIT_1_CAP}})
    (can-train {{FORT_CASTLE_UNIT_1}})
=>
    (train {{FORT_CASTLE_UNIT_1}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_CASTLE_UNIT_2}} < {{FORT_CASTLE_UNIT_2_CAP}})
    (can-train {{FORT_CASTLE_UNIT_2}})
=>
    (train {{FORT_CASTLE_UNIT_2}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_CASTLE_UNIT_3}} < {{FORT_CASTLE_UNIT_3_CAP}})
    (can-train {{FORT_CASTLE_UNIT_3}})
=>
    (train {{FORT_CASTLE_UNIT_3}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_1}} < {{CASTLE_UNIT_1_CAP}})
    (can-train {{CASTLE_UNIT_1}})
=>
    (train {{CASTLE_UNIT_1}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_2}} < {{CASTLE_UNIT_2_CAP}})
    (can-train {{CASTLE_UNIT_2}})
=>
    (train {{CASTLE_UNIT_2}})
)
(defrule
    (current-age == castle-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{CASTLE_MILITARY_TARGET}})
    (unit-type-count-total {{CASTLE_UNIT_3}} < {{CASTLE_UNIT_3_CAP}})
    (can-train {{CASTLE_UNIT_3}})
=>
    (train {{CASTLE_UNIT_3}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_IMPERIAL_UNIT_1}} < {{PRESSURE_IMPERIAL_UNIT_1_CAP}})
    (can-train {{PRESSURE_IMPERIAL_UNIT_1}})
=>
    (train {{PRESSURE_IMPERIAL_UNIT_1}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_IMPERIAL_UNIT_2}} < {{PRESSURE_IMPERIAL_UNIT_2_CAP}})
    (can-train {{PRESSURE_IMPERIAL_UNIT_2}})
=>
    (train {{PRESSURE_IMPERIAL_UNIT_2}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} >= {{PRESSURE_COUNT}})
    (military-population < {{PRESSURE_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{PRESSURE_IMPERIAL_UNIT_3}} < {{PRESSURE_IMPERIAL_UNIT_3_CAP}})
    (can-train {{PRESSURE_IMPERIAL_UNIT_3}})
=>
    (train {{PRESSURE_IMPERIAL_UNIT_3}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_IMPERIAL_UNIT_1}} < {{FORT_IMPERIAL_UNIT_1_CAP}})
    (can-train {{FORT_IMPERIAL_UNIT_1}})
=>
    (train {{FORT_IMPERIAL_UNIT_1}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_IMPERIAL_UNIT_2}} < {{FORT_IMPERIAL_UNIT_2_CAP}})
    (can-train {{FORT_IMPERIAL_UNIT_2}})
=>
    (train {{FORT_IMPERIAL_UNIT_2}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} >= {{FORT_COUNT}})
    (military-population < {{FORT_IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{FORT_IMPERIAL_UNIT_3}} < {{FORT_IMPERIAL_UNIT_3_CAP}})
    (can-train {{FORT_IMPERIAL_UNIT_3}})
=>
    (train {{FORT_IMPERIAL_UNIT_3}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_1}} < {{IMPERIAL_UNIT_1_CAP}})
    (can-train {{IMPERIAL_UNIT_1}})
=>
    (train {{IMPERIAL_UNIT_1}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_2}} < {{IMPERIAL_UNIT_2_CAP}})
    (can-train {{IMPERIAL_UNIT_2}})
=>
    (train {{IMPERIAL_UNIT_2}})
)
(defrule
    (current-age == imperial-age)
    (players-unit-type-count target-player {{PRESSURE_UNIT}} < {{PRESSURE_COUNT}})
    (players-building-type-count target-player {{FORT_BUILDING}} < {{FORT_COUNT}})
    (military-population < {{IMPERIAL_MILITARY_TARGET}})
    (unit-type-count-total {{IMPERIAL_UNIT_3}} < {{IMPERIAL_UNIT_3_CAP}})
    (can-train {{IMPERIAL_UNIT_3}})
=>
    (train {{IMPERIAL_UNIT_3}})
)
