; CLOZE TEMPLATE - rule order is research priority
(defrule
    (can-research {{ECON_TECH_1}})
=>
    (research {{ECON_TECH_1}})
)
(defrule
    (can-research {{ECON_TECH_2}})
=>
    (research {{ECON_TECH_2}})
)
(defrule
    (can-research {{ECON_TECH_3}})
=>
    (research {{ECON_TECH_3}})
)
(defrule
    (can-research {{ECON_TECH_4}})
=>
    (research {{ECON_TECH_4}})
)
(defrule
    (can-research {{ECON_TECH_5}})
=>
    (research {{ECON_TECH_5}})
)
(defrule
    (can-research {{ECON_TECH_6}})
=>
    (research {{ECON_TECH_6}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_1_UNIT}} >= {{MIL_TECH_1_MIN_COUNT}})
    (can-research {{MIL_TECH_1}})
=>
    (research {{MIL_TECH_1}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_2_UNIT}} >= {{MIL_TECH_2_MIN_COUNT}})
    (can-research {{MIL_TECH_2}})
=>
    (research {{MIL_TECH_2}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_3_UNIT}} >= {{MIL_TECH_3_MIN_COUNT}})
    (can-research {{MIL_TECH_3}})
=>
    (research {{MIL_TECH_3}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_4_UNIT}} >= {{MIL_TECH_4_MIN_COUNT}})
    (can-research {{MIL_TECH_4}})
=>
    (research {{MIL_TECH_4}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_5_UNIT}} >= {{MIL_TECH_5_MIN_COUNT}})
    (can-research {{MIL_TECH_5}})
=>
    (research {{MIL_TECH_5}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_6_UNIT}} >= {{MIL_TECH_6_MIN_COUNT}})
    (can-research {{MIL_TECH_6}})
=>
    (research {{MIL_TECH_6}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_7_UNIT}} >= {{MIL_TECH_7_MIN_COUNT}})
    (can-research {{MIL_TECH_7}})
=>
    (research {{MIL_TECH_7}})
)
(defrule
    (unit-type-count-total {{MIL_TECH_8_UNIT}} >= {{MIL_TECH_8_MIN_COUNT}})
    (can-research {{MIL_TECH_8}})
=>
    (research {{MIL_TECH_8}})
)
