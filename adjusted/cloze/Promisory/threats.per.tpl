; CLOZE TEMPLATE - fixed threat rule, AI fills hysteresis thresholds
(defrule
    (up-enemy-units-in-town >= {{THREAT_TRIGGER}})
    (town-under-attack)
=>
    (set-goal defend yes)
    (set-goal underattack yes)
)
(defrule
    (enemy-buildings-in-town)
=>
    (set-goal defend yes)
    (set-goal underattack yes)
)
(defrule
    (up-enemy-units-in-town <= {{THREAT_CLEAR}})
    (not (town-under-attack))
    (not (enemy-buildings-in-town))
=>
    (set-goal underattack no)
    (set-goal defend no)
)
