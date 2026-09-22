; CLOZE TEMPLATE - AI fills building symbols and target counts
; DARK
(defrule
    (current-age == dark-age)
    (housing-headroom < {{DARK_HOUSING_HEADROOM}})
    (population-headroom > 0)
    (up-pending-objects c: house <= 0)
    (can-build house)
=>
    (build house)
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_1}} < {{DARK_BUILDING_1_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_1}} <= 0)
    (can-build {{DARK_BUILDING_1}})
=>
    (build {{DARK_BUILDING_1}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_2}} < {{DARK_BUILDING_2_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_2}} <= 0)
    (can-build {{DARK_BUILDING_2}})
=>
    (build {{DARK_BUILDING_2}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_3}} < {{DARK_BUILDING_3_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_3}} <= 0)
    (can-build {{DARK_BUILDING_3}})
=>
    (build {{DARK_BUILDING_3}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_4}} < {{DARK_BUILDING_4_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_4}} <= 0)
    (can-build {{DARK_BUILDING_4}})
=>
    (build {{DARK_BUILDING_4}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_5}} < {{DARK_BUILDING_5_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_5}} <= 0)
    (can-build {{DARK_BUILDING_5}})
=>
    (build {{DARK_BUILDING_5}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_6}} < {{DARK_BUILDING_6_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_6}} <= 0)
    (can-build {{DARK_BUILDING_6}})
=>
    (build {{DARK_BUILDING_6}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_7}} < {{DARK_BUILDING_7_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_7}} <= 0)
    (can-build {{DARK_BUILDING_7}})
=>
    (build {{DARK_BUILDING_7}})
)
(defrule
    (current-age == dark-age)
    (building-type-count-total {{DARK_BUILDING_8}} < {{DARK_BUILDING_8_COUNT}})
    (up-pending-objects c: {{DARK_BUILDING_8}} <= 0)
    (can-build {{DARK_BUILDING_8}})
=>
    (build {{DARK_BUILDING_8}})
)

; FEUDAL
(defrule
    (current-age == feudal-age)
    (housing-headroom < {{FEUDAL_HOUSING_HEADROOM}})
    (population-headroom > 0)
    (up-pending-objects c: house <= 0)
    (can-build house)
=>
    (build house)
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_1}} < {{FEUDAL_BUILDING_1_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_1}} <= 0)
    (can-build {{FEUDAL_BUILDING_1}})
=>
    (build {{FEUDAL_BUILDING_1}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_2}} < {{FEUDAL_BUILDING_2_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_2}} <= 0)
    (can-build {{FEUDAL_BUILDING_2}})
=>
    (build {{FEUDAL_BUILDING_2}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_3}} < {{FEUDAL_BUILDING_3_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_3}} <= 0)
    (can-build {{FEUDAL_BUILDING_3}})
=>
    (build {{FEUDAL_BUILDING_3}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_4}} < {{FEUDAL_BUILDING_4_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_4}} <= 0)
    (can-build {{FEUDAL_BUILDING_4}})
=>
    (build {{FEUDAL_BUILDING_4}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_5}} < {{FEUDAL_BUILDING_5_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_5}} <= 0)
    (can-build {{FEUDAL_BUILDING_5}})
=>
    (build {{FEUDAL_BUILDING_5}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_6}} < {{FEUDAL_BUILDING_6_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_6}} <= 0)
    (can-build {{FEUDAL_BUILDING_6}})
=>
    (build {{FEUDAL_BUILDING_6}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_7}} < {{FEUDAL_BUILDING_7_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_7}} <= 0)
    (can-build {{FEUDAL_BUILDING_7}})
=>
    (build {{FEUDAL_BUILDING_7}})
)
(defrule
    (current-age == feudal-age)
    (building-type-count-total {{FEUDAL_BUILDING_8}} < {{FEUDAL_BUILDING_8_COUNT}})
    (up-pending-objects c: {{FEUDAL_BUILDING_8}} <= 0)
    (can-build {{FEUDAL_BUILDING_8}})
=>
    (build {{FEUDAL_BUILDING_8}})
)

; CASTLE
(defrule
    (current-age == castle-age)
    (housing-headroom < {{CASTLE_HOUSING_HEADROOM}})
    (population-headroom > 0)
    (up-pending-objects c: house <= 0)
    (can-build house)
=>
    (build house)
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_1}} < {{CASTLE_BUILDING_1_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_1}} <= 0)
    (can-build {{CASTLE_BUILDING_1}})
=>
    (build {{CASTLE_BUILDING_1}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_2}} < {{CASTLE_BUILDING_2_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_2}} <= 0)
    (can-build {{CASTLE_BUILDING_2}})
=>
    (build {{CASTLE_BUILDING_2}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_3}} < {{CASTLE_BUILDING_3_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_3}} <= 0)
    (can-build {{CASTLE_BUILDING_3}})
=>
    (build {{CASTLE_BUILDING_3}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_4}} < {{CASTLE_BUILDING_4_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_4}} <= 0)
    (can-build {{CASTLE_BUILDING_4}})
=>
    (build {{CASTLE_BUILDING_4}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_5}} < {{CASTLE_BUILDING_5_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_5}} <= 0)
    (can-build {{CASTLE_BUILDING_5}})
=>
    (build {{CASTLE_BUILDING_5}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_6}} < {{CASTLE_BUILDING_6_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_6}} <= 0)
    (can-build {{CASTLE_BUILDING_6}})
=>
    (build {{CASTLE_BUILDING_6}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_7}} < {{CASTLE_BUILDING_7_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_7}} <= 0)
    (can-build {{CASTLE_BUILDING_7}})
=>
    (build {{CASTLE_BUILDING_7}})
)
(defrule
    (current-age == castle-age)
    (building-type-count-total {{CASTLE_BUILDING_8}} < {{CASTLE_BUILDING_8_COUNT}})
    (up-pending-objects c: {{CASTLE_BUILDING_8}} <= 0)
    (can-build {{CASTLE_BUILDING_8}})
=>
    (build {{CASTLE_BUILDING_8}})
)

; IMPERIAL
(defrule
    (current-age == imperial-age)
    (housing-headroom < {{IMPERIAL_HOUSING_HEADROOM}})
    (population-headroom > 0)
    (up-pending-objects c: house <= 0)
    (can-build house)
=>
    (build house)
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_1}} < {{IMPERIAL_BUILDING_1_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_1}} <= 0)
    (can-build {{IMPERIAL_BUILDING_1}})
=>
    (build {{IMPERIAL_BUILDING_1}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_2}} < {{IMPERIAL_BUILDING_2_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_2}} <= 0)
    (can-build {{IMPERIAL_BUILDING_2}})
=>
    (build {{IMPERIAL_BUILDING_2}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_3}} < {{IMPERIAL_BUILDING_3_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_3}} <= 0)
    (can-build {{IMPERIAL_BUILDING_3}})
=>
    (build {{IMPERIAL_BUILDING_3}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_4}} < {{IMPERIAL_BUILDING_4_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_4}} <= 0)
    (can-build {{IMPERIAL_BUILDING_4}})
=>
    (build {{IMPERIAL_BUILDING_4}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_5}} < {{IMPERIAL_BUILDING_5_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_5}} <= 0)
    (can-build {{IMPERIAL_BUILDING_5}})
=>
    (build {{IMPERIAL_BUILDING_5}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_6}} < {{IMPERIAL_BUILDING_6_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_6}} <= 0)
    (can-build {{IMPERIAL_BUILDING_6}})
=>
    (build {{IMPERIAL_BUILDING_6}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_7}} < {{IMPERIAL_BUILDING_7_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_7}} <= 0)
    (can-build {{IMPERIAL_BUILDING_7}})
=>
    (build {{IMPERIAL_BUILDING_7}})
)
(defrule
    (current-age == imperial-age)
    (building-type-count-total {{IMPERIAL_BUILDING_8}} < {{IMPERIAL_BUILDING_8_COUNT}})
    (up-pending-objects c: {{IMPERIAL_BUILDING_8}} <= 0)
    (can-build {{IMPERIAL_BUILDING_8}})
=>
    (build {{IMPERIAL_BUILDING_8}})
)

