
;Send fish to deep fish



(defrule
    (up-idle-unit-count fishing-ship == 1)
=>
    (set-strategic-number sn-number-boat-explore-groups 0)
)

(defrule
    (timer-triggered threesec)
    (game-time < 900)
    (building-type-count dock > 0)
    (unit-type-count-total fishing-ship > 0)
=>
    (up-full-reset-search)
    (up-find-local c: dock c: 1)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-full-reset-search)
    (up-find-local c: fishing-ship c: 10)
    (up-remove-objects search-local object-data-carry > 14)
    (up-remove-objects search-local object-data-target != shore-fish-class)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point2-x)
    (up-get-point-distance point-x point2-x temporary-goal)
    (up-modify-goal temporary-goal c:+ 14);Deep fish is faster as long as it is < 14 tiles compared to the shore fish
    (up-filter-distance c: -1 c: 15)
    (up-filter-status c: status-gather c: list-active)
    (up-find-resource c: ocean-fish-class c: 10)
    (up-remove-objects search-remote object-data-carry < 15)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (up-get-search-state local-total)
    ;(up-chat-data-to-player my-player-number "Task %d fishing ships to deep fish" g: local-total)
    ;(up-chat-data-to-player my-player-number "Shore fish found %d" g: remote-total)
    (up-target-objects 0 action-default -1 -1)
)

(defrule
    (timer-triggered threesec)
    (game-time < 900)
    (building-type-count dock > 0)
    (unit-type-count-total fishing-ship > 0)
=>
    (up-full-reset-search)
    (up-find-local c: dock c: 1)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-full-reset-search)
    (up-filter-status c: status-gather c: list-active)
    (up-filter-distance c: -1 c: 25)
    (up-find-resource c: ocean-fish-class c: 1)
    (up-get-search-state local-total)
)


(defrule
    (timer-triggered threesec)
    (game-time < 900)
    (building-type-count dock > 0)
    (unit-type-count-total fishing-ship > 0)
    (up-compare-goal remote-total < 1)
=>
    (up-full-reset-search)
    (up-modify-goal point-x c:- 20)
    (up-modify-goal point-y c:- 20)
    (generate-random-number 40)
    (up-get-fact random-number 0 temporary-goal)
    (up-modify-goal point-x g:+ temporary-goal)
    (up-get-fact random-number 0 temporary-goal2)
    (up-modify-goal point-y g:+ temporary-goal)
)

(defrule
    (timer-triggered threesec)
    (game-time < 900)
    (building-type-count dock > 0)
    (unit-type-count-total fishing-ship > 0)
    (up-compare-goal remote-total < 1)
    (up-point-explored point-x c:== explored-no)
=>
    (up-find-local c: fishing-ship c: 1)
    (up-remove-objects search-local object-data-order == orderid-move)
    (up-target-point point-x action-move -1 -1)
    ;(chat-to-player my-player-number "No deep fish, scout random point near dock")
)


;Actions
;2 = move
;3 = attack
;4 = temp retreat
;5 = perpendicular movement
;6 = retreat
;7 = attack
;8 = attack dock

;Set move point (point4-x)
;galley-group-x is always point of the group

;Create group

(defrule
    (timer-triggered two-mins)
=>
    (generate-random-number 60)
    (up-get-fact random-number 0 random-factor-x)
    (generate-random-number 60)
    (up-get-fact random-number 0 random-factor-y)
)

(defrule
    (goal water-micro no)
    (up-compare-goal water-end-rule-id > 0)
=>
    (up-jump-direct g: water-end-rule-id)
)

(defrule
    (up-compare-goal disable-water-micro-turns > 0)
    (up-compare-goal water-end-rule-id > 0)
=>
    (up-modify-goal disable-water-micro-turns c:- 1)
    (up-jump-direct g: water-end-rule-id)
)



(defrule
    (up-group-size c: galley-group > 0)
=>
    (set-goal water-action -1)
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-set-target-object search-local c: 0)
    (up-get-object-data object-data-next-attack water-primary-unit-fd)
)
(defrule
    (up-group-size c: galley-group < 1)
    (unit-type-count galley-line > 0)
=>
    (up-full-reset-search)
    (up-find-local c: galley-line c: 1)
    (up-create-group 0 0 c: galley-group)    
    (up-modify-group-flag 1 c: galley-group)
    (up-set-target-object search-local c: 0)
    ;(chat-to-player my-player-number "Create group")
    ;(up-get-object-data object-data-next-attack water-primary-unit-fd)

)

;Create melee group

(defrule
    (or(unit-type-count fire-ship-line > 0)
    (unit-type-count demolition-ship-line > 0))
    (up-group-size c: water-melee-group < 1)
    (goal water-micro yes)
=>
    (up-full-reset-search)
    (up-find-local c: fire-ship-line c: 1)
    (up-find-local c: demolition-ship-line c: 1)
    (up-reset-group c: water-melee-group)
    (up-create-group 0 0 c: water-melee-group)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object water-melee-group-x);We don't have to be as accurate with this so we save performance by not doing the weighted average point
)

;Task units to melee group

(defrule
    (unit-type-count-total fire-ship-line < 10);Once we have 10 no longer send repairs
    (up-group-size c: water-melee-group > 0)
    (strategic-number sn-twenty-turns == 7)
=>
    (up-full-reset-search)
    (up-find-local c: fire-ship-line c: 40)
    (up-remove-objects search-local object-data-hitpoints < 15)
    (up-find-local c: demolition-ship-line c: 10)
    (up-remove-objects search-local object-data-group-flag == water-melee-group)
    (up-remove-objects search-local object-data-group-flag == water-runner-group)
    (up-remove-objects search-local object-data-order == orderid-attack)
    (up-target-point water-melee-group-x action-default -1 stance-aggressive);stance-no-attack
)

(defrule
    (unit-type-count-total fire-ship-line > 9);Once we have 10 no longer send repairs
    (up-group-size c: water-melee-group > 0)
    (strategic-number sn-twenty-turns == 7)
=>
    (up-full-reset-search)
    (up-find-local c: fire-ship-line c: 40)
    ;(up-remove-objects search-local object-data-hitpoints < 15)
    (up-find-local c: demolition-ship-line c: 10)
    (up-remove-objects search-local object-data-group-flag == water-melee-group)
    (up-remove-objects search-local object-data-group-flag == water-runner-group)
    (up-remove-objects search-local object-data-order == orderid-attack)
    (up-target-point water-melee-group-x action-default -1 stance-aggressive)
)

;Add units to melee group

(defrule
    (up-group-size c: water-melee-group > 0)
=>
    (up-full-reset-search)
    (up-set-target-point water-melee-group-x)
    (up-reset-group c: water-melee-group)
    (up-modify-group-flag 0 c: water-melee-group)
    (up-filter-distance c: -1 c: 7)
    (up-find-local c: fire-ship-line c: 40)
    (up-remove-objects search-local object-data-hitpoints < 15)
    (up-find-local c: demolition-ship-line c: 20)
    (up-remove-objects search-local object-data-group-flag == water-runner-group)
    (up-create-group 0 0 c: water-melee-group)
    (up-modify-group-flag 1 c: water-melee-group)
)

;Add units to low HP group

(defrule
    (up-group-size c: water-melee-group > 0)
=>
    (up-full-reset-search)
    (up-modify-group-flag 0 c: water-runner-group)
    (up-reset-group c: water-runner-group)
    (up-set-group search-local c: water-melee-group)
    (up-remove-objects search-local object-data-hitpoints > 15)
    (up-remove-objects search-local object-data-type == demolition-raft)
    (up-create-group 0 0 c: water-runner-group);Since units can't be in > 1 group in AOE2, this should take out the low HP fires from the regular group
    (up-modify-group-flag 1 c: water-runner-group)
)



;Analyze group position

(defrule
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local -1 c:> 20)
    (set-goal galley-group-x 0)
    (set-goal galley-group-y 0)
    (up-get-search-state local-total)
    (up-get-search-state temporary-goal)
    (set-goal water-advantage 0)
)

(defrule
    (up-group-size c: galley-group > 0)
    (up-compare-goal local-total > -1)
    (up-set-target-object search-local c: 0)
=>
    (up-modify-goal local-total c:- 1)
    (up-get-point position-object point2-x)
    (up-modify-goal galley-group-x g:+ point2-x)
    (up-modify-goal galley-group-y g:+ point2-y)
    (up-remove-objects search-local -1 == 0)
    (up-jump-rule -1)
)

(defrule
    (up-group-size c: galley-group > 0)
    (up-compare-goal temporary-goal > 0)
=>
    (up-modify-goal galley-group-x g:/ temporary-goal)
    (up-modify-goal galley-group-y g:/ temporary-goal)
    (up-bound-point galley-group-x galley-group-x)
    (up-get-object-data object-data-range ship-range)
)

(defrule
    (up-get-fact warboat-count 0 temporary-goal)
    (up-get-player-fact target-player unit-type-count galley-line temporary-goal2)
    (up-get-player-fact target-player unit-type-count fire-ship-line temporary-goal3)
    (up-modify-goal temporary-goal3 c:* 2)
    (up-get-player-fact target-player unit-type-count demolition-ship-line temporary-goal4)
    (up-modify-goal temporary-goal4 c:/ 2)
    (up-modify-goal temporary-goal2 g:+ temporary-goal3)
    (up-modify-goal temporary-goal4 g:+ temporary-goal4)
    (or(up-compare-goal temporary-goal g:> temporary-goal2)
    (up-group-size c: galley-group-x > 20))
    (players-building-type-count target-player dock > 0)
=>
    (up-full-reset-search)
    (up-modify-goal temporary-goal8 s:= sn-focus-player-number)
    (up-modify-sn sn-focus-player-number s:= sn-target-player-number)
    (up-find-remote c: dock c: 10)
    (up-set-target-point position-self-x)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (set-goal temporary-goal5 25876)
)

(defrule
    (goal temporary-goal5 25876)
    (up-set-target-object search-remote c: 0)
=>
    (up-get-point position-object point4-x)
    (set-goal temporary-goal5 25877)
)

(defrule
    (up-compare-goal temporary-goal g:<= temporary-goal2)
    (building-type-count dock > 0)
    (players-building-type-count target-player dock > 0)
=>
    (up-full-reset-search)
    ;(fe-break-point 1 c:== 1 -1)
    (up-get-point position-target point3-x)
    (up-find-local c: dock c: 10)
    (up-set-target-point point3-x)
    (up-clean-search search-remote object-data-distance search-order-desc)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point4-x)
    (set-goal temporary-goal5 25877)
)

(defrule
    (or(players-building-type-count target-player dock < 1)
    (not(goal temporary-goal5 25877)))
=>
    (up-get-point position-flank point4-x)
    (up-lerp-percent point4-x position-self-x c: 5);-15
    (up-modify-goal point4-x g:+ random-factor-x)
    (up-modify-goal point4-x g:+ random-factor-y) 
    (up-modify-goal point4-x c:- 30)
    (up-modify-goal point4-x c:- 30)
    (up-bound-point point4-x point4-x)
)

(defrule
    (or(up-point-distance point4-x galley-group-x < 15)
    (timer-triggered fifteensec))
    (up-point-distance point4-x galley-group-x < 3)
=>
    (generate-random-number 55)
    (up-get-fact random-number 0 random-factor-x)
    (generate-random-number 55)
    (up-get-fact random-number 0 random-factor-y)
)

(defrule
    (timer-triggered fifteensec)
    (up-point-distance point4-x galley-group-x < 25)
    (or(and(up-point-terrain point4-x != terrain-water)
    (and(up-point-terrain point4-x != terrain-water-medium)
    (up-point-terrain point4-x != terrain-water-deep)))
    (up-point-explored point4-x == explored-no))
=>
    (generate-random-number 55)
    (up-get-fact random-number 0 random-factor-x)
    (generate-random-number 55)
    (up-get-fact random-number 0 random-factor-y)
    ;(chat-to-player my-player-number "Target point unknown or not on water, randomizing new point")
)


;Add nearby units to group

(defrule
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-reset-group c: galley-group)
    (up-modify-group-flag 0 c: galley-group)
    (up-set-target-point galley-group-x)
    (up-filter-distance c: -1 c: 6)
    (up-find-local c: galley-line c: 60)
    (up-create-group 0 0 c: galley-group)
    (up-modify-group-flag 1 c: galley-group)

)

;Send units to group

(defrule
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-set-target-point galley-group-x)
    (up-filter-distance c: 7 c: -1);5
    (up-find-local c: galley-line c: 60);warship-class
    (up-remove-objects search-local object-data-next-attack > water-fd-value)
    (up-remove-objects search-local object-data-order == orderid-explore)
    (up-target-point galley-group-x action-move -1 stance-no-attack)
    (set-goal water-enemy-target-id -1)
    (set-goal water-enemy-target-type -1)
    (set-goal water-enemy-target-point-x -999)
    (set-goal water-enemy-target-point-y -999)
    (set-goal water-enemy-target-distance 999)
)

;Calculate retreat position

(defrule
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-find-local c: castle c: 1)
    (up-find-local c: watch-tower c: 1)
    (up-find-local c: dock c: 1)
    (up-find-local c: town-center c: 1)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object water-retreat-x)
    (up-bound-point point2-x galley-group-x)
    (up-lerp-percent point2-x water-retreat-x c: 75)
    (up-full-reset-search)
    (up-set-group search-local c: galley-group) 
    ;;(up-send-flare water-retreat-x)
)

(defrule
    (up-group-size c: galley-group > 0)
    (or(up-point-distance water-retreat-x galley-group-x < 5)
    (and(up-point-distance water-retreat-x galley-group-x < 15);35
    (up-point-terrain water-retreat-x != terrain-water)))
    (building-type-count-total dock > 0)
=>
    (up-full-reset-search)
    (up-find-local c: dock c: 15)
    (up-set-target-point galley-group-x)
    (up-clean-search search-local object-data-distance search-order-desc)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object water-retreat-x)
)

;Calculate enemy target and local advantage

(defrule
    (up-group-size c: galley-group > 0)
=>
    (set-strategic-number sn-focus-player-number 1)
    (set-goal water-enemy-target-id -1)
    (set-goal water-enemy-target-point-x -1)
    (set-goal water-enemy-target-point-y -1)
    (up-full-reset-search)
    (up-set-target-point galley-group-x)
    (up-modify-goal temporary-goal3 g:= ship-range)
    (up-modify-goal temporary-goal3 c:+ 8);5
    (up-filter-distance c: -1 g: temporary-goal3)
)

(defrule
    (up-group-size c: galley-group > 0)
    (player-valid focus-player)
    (stance-toward focus-player enemy)
=>
    (up-find-remote c: galley-line c: 20)
    (up-find-remote c: fire-galley-line c: 20)
    (up-find-remote c: fire-ship-line c: 20)
    (up-find-remote c: hulk-line c: 20)
    (up-find-remote c: fishing-ship c: 20)
    (up-find-remote c: transport-ship c: 20);For now, might be best to exclude ungarrisoned transports in future
    (up-find-remote c: demolition-ship-line c: 20)
    (up-find-remote c: demolition-raft c: 20)
)

(defrule
    (player-valid focus-player)
    (up-group-size c: galley-group > 0)
    (strategic-number sn-focus-player-number <= max-players)
=>
    (up-modify-sn sn-focus-player-number c:+ 1)
    (up-jump-rule -2)
)

(defrule
    (up-group-size c: galley-group > 0)
    (up-set-target-object search-remote c: 0)
=>
    (up-clean-search search-remote object-data-distance search-order-asc);axc
    (up-clean-search search-local object-data-distance search-order-desc);asc
    (up-get-search-state local-total)
    (up-set-target-object search-remote c: 0)
    (up-get-point position-object water-enemy-target-point-x)
    (up-get-object-data object-data-id water-enemy-target-id)
    (up-get-object-data object-data-class water-enemy-target-class)
    (up-get-object-data object-data-type water-enemy-target-type)
    (up-set-target-point galley-group-x)
    (up-get-object-data object-data-distance water-enemy-target-distance)
    (set-goal water-advantage 0)
)


;While we have enemy ships in memory calculate strength

;weights
;1 = demo raft
;2 = galley
;4 = fire galley, war galley, demo shpi
;6 = fast fire ship
;7 = galleon
;8 = heavy demo
(defrule
    (up-group-size c: galley-group > 0)
    (up-compare-goal remote-total > 0)
=>
    (up-remove-objects search-remote object-data-class == transport-ship-class)
    (up-remove-objects search-remote object-data-class == fishing-ship-class)
    (up-get-search-state local-total)
    (up-modify-goal water-advantage g:- remote-total)
    (up-remove-objects search-remote object-data-upgrade-type == demolition-raft)
    (up-get-search-state local-total)
    (up-modify-goal water-advantage g:- remote-total)
    (up-remove-objects search-remote object-data-upgrade-type == galley)
    (up-remove-objects search-remote object-data-type == hulk-line)
    (up-get-search-state local-total)
    (up-modify-goal remote-total c:* 2)
    (up-modify-goal water-advantage g:- remote-total)
    (up-remove-objects search-remote object-data-upgrade-type == fire-galley)
    (up-remove-objects search-remote object-data-upgrade-type == war-galley)
    (up-remove-objects search-remote object-data-upgrade-type == demolition-ship)
    (up-get-search-state local-total)
    (up-modify-goal remote-total c:* 2)
    (up-modify-goal water-advantage g:- remote-total)
    (up-remove-objects search-remote object-data-upgrade-type == fast-fire-ship)
    (up-get-search-state local-total)
    (up-modify-goal water-advantage g:- remote-total)
    (up-remove-objects search-remote object-data-upgrade-type == galleon)
    (up-get-search-state local-total)
    (up-modify-goal water-advantage g:- remote-total)
)

; (defrule    
;     (game-time > 150)
; =>
;     (fe-break-point 1 c:== 1 -1)
;     (disable-self)
; )
(defrule
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)

    (up-set-group search-local c: galley-group)
    (up-set-target-object search-local c: 0)
    (up-get-object-data object-data-next-attack primary-unit-fd)
    (up-get-search-state local-total)
    (up-modify-goal local-total c:* 2)
    (up-modify-goal water-advantage g:+ local-total)
    (up-remove-objects search-local object-data-upgrade-type == galley)
    (up-get-search-state local-total)
    (up-modify-goal local-total c:* 2)
    (up-modify-goal water-advantage g:+ local-total)
    (up-remove-objects search-local object-data-upgrade-type == war-galley)
    (up-get-search-state local-total)
    (up-modify-goal local-total c:* 2)
    (up-modify-goal water-advantage g:+ local-total)
)

;Add fire galley when melee group stuff is complete

;Choosing actions

;Attack if decent favourbility or better, target object can attack, retreat not on




;We are trying a simplification here based on the assumption that the galley frame delay (100ms) will be always less than the fastest AI turn (333ms) minus our buffer (100ms)
(defrule
    ;(nand(timer-triggered fifteensec)
    ;(goal water-action 6))
    (up-modify-goal temporary-goal s:= sn-turn-count)
    (up-modify-goal temporary-goal c:/ 100)
    (or(goal temporary-goal 4)
    (not(goal water-action 6)))
=>
    (set-goal water-action -1)
)

(defrule
    (goal water-action 6)
    (or(up-point-distance galley-group-x position-self-x < 40)
    (up-point-distance galley-group-x water-retreat-x < 12))
=>
    (set-goal water-action -1)
)



;Temporarily retreat if slight disadvantage or facing a fireship

(defrule
    (or(and(up-compare-goal water-advantage > {{WATER_ADVANTAGE_001}})
    (up-compare-goal water-advantage < {{WATER_ADVANTAGE_002}}))
    (and(up-compare-goal water-advantage < {{WATER_ADVANTAGE_003}})
    (up-compare-goal water-enemy-target-type == fire-galley)))
    (not(goal water-action 6))
    (not(goal water-action 7))
    (up-compare-goal water-primary-unit-fd > 100)
    (up-compare-goal water-primary-unit-fd < water-fd-value)
=>
    (set-goal water-action 4)
)

;Perpendicular movement if equal

(defrule
    (up-compare-goal water-advantage >= {{WATER_ADVANTAGE_004}})
    (up-compare-goal water-advantage < {{WATER_ADVANTAGE_005}})
    (not(goal water-action 4))
    (not(goal water-action 6))
    (not(goal water-action 7))
    (up-compare-goal water-primary-unit-fd > 100)
    (up-compare-goal water-primary-unit-fd < water-fd-value)
=>
    (set-goal water-action 5)
) 

;Pursue if significant advantage

(defrule
    (up-compare-goal water-advantage > {{WATER_ADVANTAGE_006}});
    (not(goal water-action 4))
    (not(goal water-action 6))
    (not(goal water-action 7))
    (not(goal water-action 5))
    (up-compare-goal water-primary-unit-fd > 100)
    (up-compare-goal water-primary-unit-fd < water-fd-value)
    (up-compare-goal water-enemy-target-id > 0)
=>
    (set-goal water-action 3)
) 

;Retreat if large disadvantage

(defrule
    (up-compare-goal water-advantage < {{WATER_ADVANTAGE_007}})
    (up-compare-goal water-primary-unit-fd < water-fd-value)
    (up-point-distance galley-group-x water-retreat-x > 12)
=>
    (set-goal water-action 6)
)

(defrule
    (or(up-research-status c: ri-bodkin-arrow == research-pending)
    (or(up-research-status c: ri-bracer == research-pending)
    (or(up-research-status c: ri-fletching == research-pending)
    (or(up-research-status c: ri-war-galley == research-pending)
    (up-research-status c: ri-galleon == research-pending)))))
    (up-compare-goal water-advantage < {{WATER_ADVANTAGE_008}})
=>
    (set-goal water-action 6)
    )


(defrule
    (true)
=>
    (up-full-reset-search)
    (up-filter-distance c: -1 c: 15)
    (up-set-target-point galley-group-x)
    (set-goal remote-total 0)
    (set-strategic-number sn-focus-player-number 1)
)

(defrule
    (up-compare-goal remote-total < 1)
    (up-compare-sn sn-focus-player-number < max-players)
=>
    (up-find-remote c: castle c: 1)
    (up-modify-sn sn-focus-player-number c:+ 1)
    (up-get-search-state local-total)
    (up-jump-rule -1)
)

(defrule
    (or(up-compare-goal remote-total > 0)
    (up-projectile-detected projectile-castle < 15000))
=>
    (set-goal water-action 6)
    ;(set-goal disable-water-micro-turns 30)
    (up-reset-search 1 1 0 0)
    (up-find-local c: cannon-galleon-line c: 5)
    (up-target-objects 0 action-default -1 -1)
    (up-full-reset-search)
)

(defrule
    (up-compare-goal water-advantage > {{WATER_ADVANTAGE_009}})
    (not(goal water-action 6))
    (up-compare-goal water-primary-unit-fd < 100);Experiment without this condition
    (up-modify-goal temporary-goal g:= water-enemy-target-distance)
    (up-modify-goal temporary-goal c:- 1)
    (up-compare-goal ship-range g:>= temporary-goal)
    (up-compare-goal temporary-goal >= -1)
=>
    (set-goal water-action 7)
)

;Attack enemies
(defrule
    (up-compare-goal water-action < 3)
=>
    (up-modify-sn sn-focus-player-number s:= sn-target-player-number)
    (up-full-reset-search)
    (up-set-target-point galley-group-x)
    ;(up-filter-include 4 -1 -1 -1)
    (up-modify-goal temporary-goal g:= ship-range)
    (up-modify-goal temporary-goal c:- 1);2
    (up-filter-distance c: -1 g: temporary-goal)
    (up-find-remote c: villager-class c: 10)
    (up-find-remote c: monastery-class c: 10)
    (up-filter-include 4 -1 -1 -1)
    (up-find-remote c: all-units-class c: 10)
    (up-remove-objects search-remote object-data-class == warship-class)
    (up-get-search-state local-total)
)

(defrule
    (or(goal water-action 6)
    (goal water-action -1))
    (up-compare-goal water-primary-unit-fd < 100)
    (up-point-distance galley-group-x water-retreat-x < 10)
    (up-compare-goal water-enemy-target-id > 0)
=>
    (set-goal water-action 7)
    ;(chat-to-player my-player-number "Nowhere to retreat. Attack")
)
(defrule
    (up-compare-goal water-action < 3)
    (up-compare-goal remote-total > 0)
    (or(up-compare-goal water-advantage > 10);10
    (and(up-compare-goal water-advantage > 0)
    (up-compare-goal water-enemy-target-id < 0)))
=>
    (set-goal water-action 9)
)

(defrule
    (true)
=>
    (up-full-reset-search)
    (up-filter-distance c: -1 c: 15)
    (up-set-target-point galley-group-x)
    (up-modify-sn sn-focus-player-number s:= sn-target-player-number)
)

(defrule
    (up-compare-goal water-action <= 3)
    (up-compare-goal water-advantage > {{WATER_ADVANTAGE_010}})
    (up-compare-goal water-primary-unit-fd < 100)
    (or(up-find-remote c: dock c: 1)
    (or(up-find-remote c: donjon c: 1)
    (up-find-remote c: watch-tower c: 1)))
    (up-compare-goal water-enemy-target-id < 1)
=>
    (set-goal water-action 8)
)



        
;Move if no other action is available

(defrule
    (up-modify-goal temporary-goal g:= water-enemy-target-distance)
    (up-modify-goal temporary-goal c:+ 3)
    (or(up-compare-goal water-action < 1)
    (up-compare-goal water-action > 9))
    (or(up-compare-goal water-primary-unit-fd > 0)
    (or(up-compare-goal ship-range g:<= temporary-goal)
    (up-compare-goal water-enemy-target-id <= 0)))
=>
    (set-goal water-action 2)
)

(defrule
    (goal water-action -1)
    (up-compare-goal water-enemy-target-id > 0)
=>
    (set-goal water-action 7)
)
;Debug rule



;Action 2 - move

(defrule
    (goal water-action 2)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-next-attack >= water-fd-value)
    (up-target-point point4-x action-move -1 stance-no-attack)
)

(defrule
    (goal water-action 2)
    (up-group-size c: water-melee-group > 0)
=>
    (up-full-reset-search)
    (up-bound-point point-x point4-x)
    (up-lerp-tiles point-x enemy-x c: 2)
    (up-set-group search-local c: water-melee-group)
    (up-remove-objects search-local object-data-order == orderid-attack);Experiment with allowing attacking while moving for fships
    (up-target-point point-x action-move -1 stance-aggressive);stance-no-attack
)

;Action 3 - track/pursue enemy

(defrule
    (goal water-action 3)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-target-point water-enemy-target-point-x action-move -1 stance-no-attack)
)

;Action 4 - Temporarily retreat

;Do we need to adjust the point if on land?

;TODO Consider spread formation against demos
(defrule
    (goal water-action 4)
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-next-attack >= water-fd-value)
    (up-bound-point point2-x galley-group-x)
    (up-lerp-tiles point2-x water-enemy-target-point-x c: -5)
    (up-target-point point2-x action-move -1 stance-no-attack)
)

;Action 5 - Perpendicular movement

(defrule
    (goal water-action 5)
    (up-group-size c: galley-group > 0)
    (up-compare-sn sn-twenty-turns < 10)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-next-attack >= water-fd-value)
    (up-remove-objects search-local object-data-id g:== runner-id)
    (up-bound-point point2-x galley-group-x)
    (up-cross-tiles point2-x water-enemy-target-point-x c: -5)
    (up-target-point point2-x action-move -1 stance-no-attack)
)

(defrule
    (goal water-action 5)
    (up-group-size c: galley-group > 0)
    (up-compare-sn sn-twenty-turns > 9)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-next-attack >= water-fd-value)
    (up-remove-objects search-local object-data-id g:== runner-id)
    (up-bound-point point2-x galley-group-x)
    (up-cross-tiles point2-x water-enemy-target-point-x c: 5)
    (up-target-point point2-x action-move -1 stance-no-attack)
)

;Action 6 - full retreat

(defrule
    (goal water-action 6)
    (up-group-size c: galley-group > 0)
    (or(strategic-number sn-twenty-turns < 5)
    (not(up-projectile-detected projectile-ship < 1000)))
    (not(timer-triggered threesec))
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group) 
    (up-remove-objects search-local object-data-order == orderid-move)
    (up-remove-objects search-local object-data-next-attack > water-fd-value)
    (up-target-point water-retreat-x action-move formation-line stance-no-attack)
    (up-jump-rule 2)
)

(defrule
    (goal water-action 6)
    (up-group-size c: galley-group > 0)
    (or(strategic-number sn-twenty-turns < 5)
    (not(up-projectile-detected projectile-ship < 1000)))
    (timer-triggered threesec)
=>

    (up-full-reset-search)
    (up-set-group search-local c: galley-group) 
    ;;(up-send-flare point3-x)
    (up-remove-objects search-local object-data-next-attack > water-fd-value)
    (up-target-point water-retreat-x action-move formation-line stance-no-attack)
    (up-jump-rule 1)
)

(defrule
    (goal water-action 6)
    (up-group-size c: galley-group > 0)
    (strategic-number sn-twenty-turns > 4)
    (up-projectile-detected projectile-ship < 1000)
    (timer-triggered threesec)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group) 
    (up-remove-objects search-local object-data-next-attack > water-fd-value)
    (up-target-point water-retreat-x action-move formation-flank stance-no-attack)
)

(defrule
    (goal water-action 6)
    (up-group-size c: galley-group > 0)
    (up-group-size c: water-melee-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: water-melee-group)
    (up-target-point water-retreat-x action-move formation-line stance-no-attack)
)

;Action 7 - attack

(defrule
    (goal water-action 7)
    (up-group-size c: galley-group > 0)
    (or(up-group-size c: galley-group < 21)
    (players-unit-type-count target-player fire-ship-line > 0))
=>
    (up-full-reset-search)
    (up-add-object-by-id search-remote g: water-enemy-target-id)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-next-attack > 0)
    (up-target-objects 0 action-default -1 stance-no-attack)
    (up-jump-rule 1)
)


;When > 9 ships, use attack move micro instead
(defrule
    (goal water-action 7)
    (up-group-size c: galley-group > 0)
    (up-group-size c: galley-group > 20)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-id g:== runner-id)
    (up-remove-objects search-local object-data-next-attack > 0)
    ;(up-remove-objects search-local object-data-order == orderid-stop)
    ;(up-remove-objects search-local object-data-order == orderid-attack)
    (up-target-point water-enemy-target-point-x action-attack-move -1 stance-aggressive)
    (set-goal disable-water-micro-turns 3)
)

(defrule
    (or(goal water-action 8)
    (or(goal water-action 3)
    (or(goal water-action 4)
    (or(goal water-action 5)
    (goal water-action 7)))))
    (up-group-size c: water-melee-group > 0)
    (up-group-size c: galley-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: water-melee-group)
    ;(up-remove-objects search-local object-data-next-attack > 0)
    (up-remove-objects search-local object-data-order == orderid-attack-move)
    (up-remove-objects search-local object-data-order == orderid-attack)
    (up-target-point water-enemy-target-point-x action-attack-move formation-line stance-aggressive)
) 
;Action 8 - target the dock/shore towers

(defrule
    (goal water-action 8)
    (up-group-size c: galley-group > 0)
    ;(timer-triggered threesec)
=>
    (up-full-reset-search)
    (up-filter-distance c: -1 c: 15)
    (up-set-target-point galley-group-x)
    (up-set-group search-local c: galley-group)
    (up-find-remote c: watch-tower c: 1)
    (up-find-remote c: donjon c: 1)
    (up-find-remote c: dock c: 5)
    (up-reset-filters)
    (up-filter-distance c: -1 c: 7)
    (up-find-remote c: villager-class c: 1)
    ;(up-filter-include 4 -1 -1 -1)
    ;(up-find-remote c: all-units-class c: 1)
    (up-clean-search search-remote object-data-hitpoints search-order-asc) 
    (up-remove-objects search-remote -1 > 0)
    (up-target-objects 0 action-default -1 stance-no-attack)
)

; (defrule
;     (goal water-action 9)
; =>
;     (fe-break-point 1 c:== 1 -1)
;     (disable-self)
; )
;Action 9 - attack enemy stuff

(defrule
    (goal water-action 9)
=>
    (up-full-reset-search)
    (up-set-group search-local c: galley-group)
    (up-remove-objects search-local object-data-order == orderid-attack-move)
    (up-remove-objects search-local object-data-order == orderid-attack)
    (up-target-point enemy-x action-attack-move -1 stance-aggressive)
    (set-goal disable-water-micro-turns 3)
)

;Injured fireships actions

(defrule
    (unit-type-count-total fire-ship-line < 12)
    (up-group-size c: water-runner-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: water-runner-group)
    (up-target-point water-retreat-x action-move formation-flank stance-no-attack)
)

(defrule
    (unit-type-count-total fire-ship-line < 6)
    (up-group-size c: water-runner-group > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: water-runner-group)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-full-reset-search)
    (up-set-group search-remote c: water-runner-group)
    (up-filter-distance c: -1 c: 20)
    (up-find-local c: villager-class c: 1)
    (up-target-objects 0 action-default -1 -1);repair
)

(defrule
    (true)
=>
    (up-get-rule-id water-end-rule-id)
)

(defrule
    (not(goal inseln yes))
=>
    (up-jump-rule 45)
)

(defrule
    (goal market-placement stage1)
    (unit-type-count transport-ship-class > 0)
    (wood-amount > 300)
    (building-type-count-total market < 6);3
=>
    (up-full-reset-search)
    (up-filter-range -1 1 -1 -1)
    (up-find-local c: transport-ship-class c: 1)
    (up-get-search-state local-total)
)

(defrule
    (goal market-placement stage1)
    (unit-type-count transport-ship-class > 0)
    (wood-amount > 300)
    (unit-type-count villager > 15)
    (building-type-count-total market < 6)
    (up-compare-goal local-total > 0)
    (up-set-target-object search-local c: 0)
    (up-compare-goal transport-exclude-id < 1)
=>
    (up-get-object-data object-data-id transport-exclude-id)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-full-reset-search)
    (up-add-object-by-id search-remote g: transport-exclude-id)
    (up-find-local c: villager-class c: 10)
    (up-filter-exclude -1 actionid-build orderid-build -1)
    (up-clean-search search-local object-data-distance search-order-asc)
    (up-remove-objects search-local -1 > 0)
    (up-target-objects 0 action-garrison -1 -1)
)

(defrule
    (goal market-placement stage1)
    (up-compare-goal transport-exclude-id > 0)
    (up-set-target-by-id g: transport-exclude-id)
    (up-object-data object-data-garrison-count > 0)
    (up-object-data object-data-order != orderid-unload)
=>
 ;   (fe-break-point 1 c:== 1 -1)
    (set-goal market-placement stage2)
    (up-full-reset-search)
    (up-add-object-by-id search-local g: transport-exclude-id)
    (up-find-player ally find-closest temporary-goal)
 ;   (up-chat-data-to-player 1 "Trying to transport to ally %d" g: temporary-goal)
    (up-modify-sn sn-focus-player-number g:= temporary-goal)
    (up-find-remote c: town-center c: 1)
    (up-set-target-object search-remote c: 0)
    (up-get-point position-object point-x)
    (up-lerp-tiles point-x position-self-x c: 10)
    (up-target-point point-x action-unload -1 -1)
;    ;(up-send-flare point-x)
)

(defrule
    (goal market-placement stage2)
    (up-set-target-by-id g: transport-exclude-id)
    (up-object-data object-data-garrison-count < 1)
=>
    (set-goal market-placement stage3)
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 0)
    (up-find-local c: villager-class c: 1)
)

(defrule
    (goal market-placement stage3)
=>
    (up-get-point-zone position-self-x temporary-goal8)
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 0)
    (up-find-local c: villager-class c: 1)
)
(defrule
    (goal market-placement stage3)
    (up-set-target-object search-local c: 0)
    (up-pending-objects c: market < 2)
    (building-type-count-total market < 6)
=>
    (up-get-point position-object point-x)
    (up-modify-goal temporary-goal11 s:= sn-focus-player-number)
    (up-find-player ally find-closest temporary-goal)
    (up-modify-sn sn-focus-player-number g:= temporary-goal)
    (up-get-point position-focus point2-x)
    (up-lerp-tiles point-x point2-x c: 5)
    (set-goal temporary-goal2 2468)
    (set-goal temporary-goal3 10)
    (set-goal temporary-goal4 10)
    (up-modify-sn sn-focus-player-number g:= temporary-goal11)
)


(defrule
    (goal market-placement stage3)
    (goal temporary-goal2 2468)
    (up-can-build-line point-x point-x c: market)
    (up-point-zone point-x g:!= temporary-goal8)
    (up-pending-objects c: market < 1)
=>
    (up-build-line point-x point-x c: market)
    (up-jump-rule 1)
)

(defrule
    (up-compare-goal temporary-goal4 > 0)
    (goal temporary-goal2 2468)
    (goal market-placement stage3)
    (building-type-count-total market < 3)
    (up-compare-goal temporary-goal3 > 0)
=>
    (generate-random-number 3)
    (up-get-fact random-number 0 temporary-goal5)
    (generate-random-number 3)
    (up-get-fact random-number 0 temporary-goal6)
    (up-modify-goal point-x c:- 2)
    (up-modify-goal point-y c:- 2)
    (up-modify-goal point-x g:+ temporary-goal5)
    (up-modify-goal point-y g:+ temporary-goal6)
    (up-modify-goal temporary-goal4 c:- 1)
    (up-jump-rule -2)
)
(defrule
    (goal market-placement stage3)
    (goal temporary-goal2 2468)
    (up-pending-objects c: market < 2)
    (building-type-count-total market < 3)
    (up-compare-goal temporary-goal3 > 0)
=>
    (up-lerp-tiles point-x position-self-x c: 1)
    (up-modify-goal temporary-goal3 c:- 1)
    (up-jump-rule -3)
)

(defrule
    (goal market-placement stage3)
    (up-pending-objects c: market < 1)
=>
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 0)
    (up-find-local c: market c: 1)
    (up-get-search-state local-total)
)

(defrule
    (goal market-placement stage3)
    (up-pending-objects c: market < 1)
    (up-compare-goal local-total > 0)
=>
    (set-goal market-placement stage4)
    (up-full-reset-search)
    (up-add-object-by-id search-remote g: transport-exclude-id)
    (up-filter-include -1 -1 -1 0)
    (up-find-local c: villager-class c: 1)
    (up-target-objects 0 action-garrison -1 -1)
    (up-target-objects 0 action-delete -1 -1)
    (set-goal transport-exclude-id -1)
)

; (defrule
;     (goal market-placement stage4)
;     (up-set-target-by-id g: transport-exclude-id)
;     (up-object-data object-data-garrison-count > 0)
; =>
;     (up-full-reset-search)
;     (set-goal market-placement market-complete)
;     (up-get-point position-object point-x)
;     (up-lerp-percent point-x position-self-x c: 80)
;     (up-target-point point-x action-unload -1 -1)
;     (set-goal transport-exclude-id -1)
; )




(defrule
    (game-time > 240)
    (timer-triggered threesec)
    (or(population > 193)
    (up-compare-sn sn-military-superiority > 1))
    (unit-type-count-total transport-ship-class > 1)
    (up-compare-goal external-gatherers-stage < 2)
    (or(players-building-type-count every-ally market < 1)
    (up-compare-goal market-placement >= stage4))
=>
    (set-goal external-gatherers-stage 2)
    ;(chst-to-allies "EG: 2")
)

(defrule
    (goal external-gatherers-stage 2)
    (up-compare-goal transport-exclude-id < 0)
    (up-group-size c: external-gold-gatherers < 1)
=>
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 0)
    (up-set-target-point enemy-x)
    (up-filter-distance c: 30 c: 200);35
    (up-filter-status c: status-resource c: list-active)
    (up-find-resource c: gold c: 15)
    (up-set-target-point position-self-x)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (up-find-player ally find-closest temporary-goal5)
    (up-modify-goal temporary-goal6 s:= sn-focus-player-number)
    (up-modify-sn sn-focus-player-number g:= temporary-goal5)
    (up-get-point position-focus point2-x)
    (up-get-point position-object point-x)
    (up-get-point-zone point2-x temporary-goal8)
    (up-set-target-point point2-x)
    ;(up-send-flare point2-x)
    (up-remove-objects search-remote object-data-distance < 32)
    (up-remove-objects search-remote object-data-map-zone-id g:== temporary-goal8)
    (up-get-search-state local-total)
    (up-modify-sn sn-focus-player-number g:= temporary-goal6)
)

(defrule
    (goal external-gatherers-stage 2)
    (up-compare-goal transport-exclude-id < 0)
    (up-group-size c: external-gold-gatherers < 1)
    (up-set-target-object search-remote c: 0)
    (unit-type-count villager > 40)
    (up-compare-goal remote-total > 0)
    (unit-type-count transport-ship-class > 0)
    (up-point-distance point-x center-x < 35);45
=>
    (up-get-point position-object gold-x)
    (up-get-object-data object-data-id gold-id)
    ;(up-send-flare gold-x)
    (up-reset-filters)
    (up-filter-exclude -1 actionid-build orderid-build -1)
    (up-find-local c: villager-class c: 10);5
    (up-create-group 0 0 c: external-gold-gatherers)
    (up-modify-group-flag 1 c: external-gold-gatherers)
    (up-modify-goal temporary-goal8 s:= sn-focus-player-number)
    (up-reset-search 0 0 1 1)
    (up-reset-filters)
    (set-strategic-number sn-focus-player-number my-player-number)
    (up-find-remote c: transport-ship-class c: 1)
    (up-set-target-object search-remote c: 0)
    (up-get-object-data object-data-id transport-exclude-id)
    (up-modify-sn sn-focus-player-number g:= temporary-goal8)
    (set-goal external-gatherers-stage 3)
    ;(chst-to-allies "EG: 3")
)

(defrule
    (goal external-gatherers-stage 3)
    (up-compare-goal transport-exclude-id > 0)
=>
    (up-full-reset-search)
    (up-add-object-by-id search-remote g: transport-exclude-id)
    (up-set-group search-local c: external-gold-gatherers)
    (up-target-objects 0 action-garrison -1 -1)
)

(defrule
    (goal external-gatherers-stage 3)
    (up-compare-goal transport-exclude-id > 0)
    (timer-triggered one-min)
=>
    (up-full-reset-search)
    (up-add-object-by-id search-remote g: transport-exclude-id)
    (up-filter-exclude -1 actionid-build orderid-enter -1)
    (up-find-local c: villager-class c: 1)
    (up-target-objects 0 action-garrison -1 -1)
)
(defrule
    (or(goal external-gatherers-stage 3)
    (goal external-gatherers-stage 4))
    (up-set-target-by-id g: transport-exclude-id)
    (up-object-data object-data-garrison-count > 9);4
    (timer-triggered threesec)
    (up-compare-goal transport-exclude-id > 0)
=>
    (up-full-reset-search)
    (up-add-object-by-id search-local g: transport-exclude-id)
    (up-target-point gold-x action-unload -1 -1)
    ;(up-send-flare gold-x)
    (set-goal external-gatherers-stage 4)
    ;(chst-to-allies "EG: 4")
)

(defrule
    (goal external-gatherers-stage 4)
    (up-object-data object-data-garrison-count < 1)

    (up-compare-goal transport-exclude-id > 0)
=>
    (set-goal external-gatherers-stage 5)
    ;(chst-to-allies "EG: 5")
)

(defrule
    (goal external-gatherers-stage 5)
    (up-compare-goal transport-exclude-id > 0)
=>
    (set-goal temporary-goal3 8)
    (up-bound-point input-point-x gold-x)
)

(defrule
    (goal external-gatherers-stage 5)
    (up-can-build-line 0 input-point-x c: gold-building)
    (up-compare-goal transport-exclude-id > 0)
=>
    (up-build-line input-point-x input-point-x c: gold-building)
    (up-assign-builders c: mining-camp c: 5)
    (set-goal external-gatherers-stage 6)
    ;(up-send-flare input-point-x)
    ;(chst-to-allies "EG: 6")
    (up-jump-rule 1)
)

(defrule
    (goal external-gatherers-stage 5)
    (can-afford-building mining-camp)
    (up-compare-goal temporary-goal3 > 0)
    (up-compare-goal transport-exclude-id > 0)
=>
    (up-modify-goal temporary-goal3 c:- 1)
    (up-bound-point input-point-x gold-x)
    (set-goal point-variance 8)
    (up-modify-goal point-variance g:- temporary-goal3)
    (xs-script-call "ApplyRandomnessToPoint")
    (up-jump-rule -2)
)

(defrule
    (goal external-gatherers-stage 6)
    (timer-triggered fifteensec)
    (up-group-size c: external-gold-gatherers > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: external-gold-gatherers)
    (up-filter-status c: status-resource c: list-active)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-filter-distance c: -1 c: 20)
    (up-remove-objects search-local object-data-target == gold-mine-class)
    (up-remove-objects search-local object-data-order == orderid-build)
    (up-find-resource c: gold c: 15)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (up-remove-objects search-remote -1 > 0)
    (up-get-search-state local-total)
    (up-target-objects 0 action-default -1 -1)
)

(defrule
    (goal external-gatherers-stage 6)
    (up-compare-goal remote-total < 1)
    (up-group-size c: external-gold-gatherers > 0)
    (timer-triggered fifteensec)
    (can-build lumber-camp)
=>
    (up-reset-filters)
    (up-reset-search 0 0 1 1)
    (up-filter-distance c: -1 c: 20)
    (up-filter-status c: status-ready c: list-active)
    (up-find-resource c: wood c: 20)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (set-goal remote-total 0)
    (up-get-search-state local-total)
    (set-goal temporary-goal3 10)
)


(defrule
    (goal external-gatherers-stage 6)
    (up-compare-goal remote-total < 1)
    (up-group-size c: external-gold-gatherers > 0)
    (timer-triggered fifteensec)
    (can-build lumber-camp)
    (up-compare-goal remote-total > 0)
    (up-set-target-object search-remote c: 0)
=>
    (set-goal external-gatherers-stage 7)
    (up-get-point position-object input-point-x)
    (up-get-point position-object gold-x)
)

(defrule
    (goal external-gatherers-stage 7)
    (timer-triggered fifteensec)
=>
    (set-goal temporary-goal3 8)
    (up-bound-point input-point-x gold-x)
)

(defrule
    (goal external-gatherers-stage 8)
    (up-can-build-line 0 input-point-x c: wood-building)
    (up-compare-goal transport-exclude-id > 0)
    (timer-triggered fifteensec)
=>
    (up-build-line input-point-x input-point-x c: wood-building)
    (up-assign-builders c: lumber-camp c: 5)
    (set-goal external-gatherers-stage 9)
    ;(up-send-flare input-point-x)
    ;(chst-to-allies "EG: 9")
    (up-jump-rule 1)
)

(defrule
    (goal external-gatherers-stage 8)
    (can-afford-building lumber-camp)
    (up-compare-goal temporary-goal3 > 0)
    (up-compare-goal transport-exclude-id > 0)
    (timer-triggered fifteensec)
=>
    (up-modify-goal temporary-goal3 c:- 1)
    (up-bound-point input-point-x gold-x)
    (set-goal point-variance 8)
    (up-modify-goal point-variance g:- temporary-goal3)
    (xs-script-call "ApplyRandomnessToPoint")
    (up-jump-rule -2)
)

(defrule
    (goal external-gatherers-stage 9)
    (timer-triggered fifteensec)
    (up-group-size c: external-gold-gatherers > 0)
=>
    (up-full-reset-search)
    (up-set-group search-local c: external-gold-gatherers)
    (up-filter-status c: status-ready c: list-active)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-filter-distance c: -1 c: 20)
    (up-remove-objects search-local object-data-target == tree-class)
    (up-remove-objects search-local object-data-order == orderid-build)
    (up-find-resource c: wood c: 15)
    (up-clean-search search-remote object-data-distance search-order-asc)
    (up-remove-objects search-remote -1 > 0)
    (up-get-search-state local-total)
    (up-target-objects 0 action-default -1 -1)
)

(defrule
    (timer-triggered threesec)
    (goal inseln yes)
    (current-age == imperial-age)
    (or(and(population > max-civ-pop)
    (wood-amount > 700))
    (or(population > 195)
    (strategic-number sn-military-superiority > 1)))
    (nand(up-compare-goal gl-threat-time < 10000)
    (goal attacking no))
    (or(current-age-time > 300)
    (or(players-building-type-count every-ally market < 1)
    (up-compare-goal market-placement >= stage4)))
=>
    (up-full-reset-search)
    (up-filter-include 4 -1 -1 1)
    (up-find-local c: all-units-class c: 59)
    (up-reset-filters)
    (up-modify-goal temporary-goal7 s:= sn-focus-player-number)
    (set-strategic-number sn-focus-player-number my-player-number)
    (up-set-target-point position-self-x)
    (up-filter-range -1 20 -1 100)
    (up-find-remote c: transport-ship-class c: 5)
    (up-remove-objects search-remote object-data-id g:== transport-exclude-id)
    (up-target-objects 0 action-garrison -1 -1)
    (set-goal temporary-goal2 98456)
    (up-modify-sn sn-focus-player-number g:= temporary-goal7)
)

(defrule
    (timer-triggered two-mins)
    (goal inseln yes)
    (current-age == imperial-age)
    (or(and(population > max-civ-pop)
    (wood-amount > 700))
    (or(population > 192)
    (strategic-number sn-military-superiority > 1)))
    (nand(up-compare-goal gl-threat-time < 10000)
    (goal attacking no))
=>
    (up-full-reset-search)
    (up-filter-include 4 -1 -1 -1)
    (up-find-local c: all-units-class c: 59)
    (up-remove-objects search-local object-data-class == transport-ship-class)
    (up-reset-filters)
    (up-get-point-zone enemy-x temporary-goal2)
    ;(up-send-flare enemy-x)
    ;(up-chat-data-to-player 1 "Exclude zone: %d" g: temporary-goal2)
    (up-get-point-zone position-self-x temporary-goal3)
    (up-remove-objects search-local object-data-map-zone-id g:== temporary-goal2)
    (up-modify-goal temporary-goal7 s:= sn-focus-player-number)
    (set-strategic-number sn-focus-player-number my-player-number)
    (up-set-target-point position-self-x)
    (up-filter-range -1 20 -1 -1)
    (up-find-remote c: transport-ship-class c: 5)
    (up-remove-objects search-remote object-data-id g:== transport-exclude-id)
    (up-target-objects 0 action-garrison -1 -1)
    (set-goal temporary-goal2 98456)
    (up-modify-sn sn-focus-player-number g:= temporary-goal7)
)
(defrule
    (goal temporary-goal2 98456)
    (not(up-set-target-by-id g: fwd-villager-id))
    (unit-type-count villager > 30)
=>
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 1)
    (up-filter-exclude -1 actionid-build orderid-build -1)
    (up-find-local c: villager-class c: 1)
    (up-remove-objects search-local object-data-group-flag == external-gold-gatherers)
    (up-remove-objects search-local object-data-order == orderid-enter)
)

(defrule
    (goal temporary-goal2 98456)
    (not(up-set-target-by-id g: fwd-villager-id))
    (unit-type-count villager > 30)
    (up-set-target-object search-local c: 0)
=>
    (up-get-object-data object-data-id fwd-villager-id)
)

(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
=>
    (up-full-reset-search)
    (up-add-object-by-id search-local g: fwd-villager-id)
    (up-remove-objects search-local object-data-on-mainland != 1)
    (up-modify-goal temporary-goal7 s:= sn-focus-player-number)
    (set-strategic-number sn-focus-player-number my-player-number)
    (up-set-target-point position-self-x)
    (up-filter-range -1 20 -1 100)
    (up-find-remote c: transport-ship-class c: 3)
    (up-remove-objects search-remote object-data-id g:== transport-exclude-id)
    (up-clean-search search-remote object-data-garrison-count search-order-desc)
    (up-remove-objects search-remote -1 > 0)
    (up-target-objects 0 action-garrison -1 -1)
    (set-goal temporary-goal2 98456)
    (up-modify-sn sn-focus-player-number g:= temporary-goal7)
)

(defrule
    (goal temporary-goal2 98456)
    (unit-type-count warship-class > 0)
=>
    (generate-random-number 4)
    (up-full-reset-search)
    (up-modify-goal temporary-goal7 s:= sn-focus-player-number)
    (up-set-target-point enemy-x)
    (up-find-local c: warship-class c: 10)
    (up-find-local c: cannon-galleon c: 10)
    (up-clean-search search-local object-data-distance search-order-asc)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
    (up-set-target-point point-x)
    (up-lerp-percent point-x enemy-x c: 60);40
    (up-get-point position-target point2-x)
    (up-get-point-zone point2-x temporary-goal5)
    (up-set-target-point point-x)
    (up-modify-sn sn-focus-player-number s:= sn-target-player-number)
    (up-filter-distance c: -1 c: 15)
    (up-find-remote c: castle c: 1)
    (up-get-search-state local-total)
)

(defrule
    (goal temporary-goal2 98456)
    (unit-type-count-total warship-class > 0)
    (up-point-zone point-x g:== temporary-goal5)
    (or(up-compare-goal remote-total < 1)
    (or(gold-amount > 1000)
    (wood-amount > 2000)))
=>
    (up-full-reset-search)
    (up-filter-range 20 -1 -1 -1)
    (up-find-local c: transport-ship-class c: 5)
    (up-target-point point-x action-unload -1 -1)
)

(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
    (wood-amount > 200)
=>
    (up-full-reset-search)
    (up-add-object-by-id search-local g: fwd-villager-id)
    (up-remove-objects search-local object-data-on-mainland == 1)
    (up-get-search-state local-total)
    (up-set-target-object search-local c: 0)
    (up-get-point position-object point-x)
)

(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
    (wood-amount > 200)
    (research-completed ri-plate-mail)
    (up-compare-goal local-total > 0)
    (up-can-build-line 0 point-x c: barracks)
    (building-type-count-total barracks < 9)
=>
    (up-full-reset-search)
    (up-bound-point point-x point-x)
    (up-build-line point-x point-x c: barracks)
)

(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
    (wood-amount > 200)
    (research-completed ri-bracer)
    (up-compare-goal local-total > 0)
    (up-can-build-line 0 point-x c: barracks)
    (building-type-count-total archery-range < 9)
=>
    (up-full-reset-search)
    (up-bound-point point-x point-x)
    (up-build-line point-x point-x c: archery-range)
)

(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
    (wood-amount > 200)
    (research-completed ri-plate-barding)
    (up-compare-goal local-total > 0)
    (up-can-build-line 0 point-x c: stable)
    (building-type-count-total stable < 9)
=>
    (up-full-reset-search)
    (up-bound-point point-x point-x)
    (up-build-line point-x point-x c: stable)
)


(defrule
    (goal temporary-goal2 98456)
    (up-set-target-by-id g: fwd-villager-id)
    (wood-amount > 200)
    (research-completed ri-siege-ram)
    (up-compare-goal local-total > 0)
    (up-can-build-line 0 point-x c: siege-workshop)
    (building-type-count-total siege-workshop < 5)
=>
    (up-full-reset-search)
    (up-bound-point point-x point-x)
    (up-build-line point-x point-x c: siege-workshop)
)

(defrule
    (timer-triggered one-min)
    (goal inseln yes)
=>
    (up-full-reset-search)
    (up-set-target-point position-self-x)
    (up-filter-distance c: -1 c: 50)
    (up-filter-include -1 -1 -1 1)
    (up-find-resource c: wood c: 20)
    (up-filter-status c: status-resource c: list-active)
    (up-find-resource c: gold c: 15)
    (up-find-resource c: stone c: 5)
    (up-get-search-state local-total)
)

(defrule
    (timer-triggered one-min)
    (goal inseln yes)
    (up-compare-goal remote-total < 15)
=>
    (set-goal island-resources-low yes)
)

(defrule
    (goal island-resources-low yes)
    (population >= eighty-pop)
    (up-idle-unit-count idle-type-villager >= 5)
    (unit-type-count villager > 40)
    (or(players-building-count target-player > 0)
    (players-unit-count target-player > 0))
=>
    (up-full-reset-search)
    (up-filter-include -1 -1 -1 1)
    (up-find-local c: villager-class c: 20)
    (up-remove-objects search-local object-data-order == orderid-build)
    (up-remove-objects search-local object-data-action == actionid-gather);an orderid might be old
    (up-remove-objects search-local object-data-order == orderid-attack)
    (up-modify-sn sn-focus-player-number s:= sn-target-player-number)
    (up-find-remote c: all-units-class c: 1)
    (up-target-objects 0 action-delete -1 -1)
)

(defrule
    (timer-triggered ten-mins)
    (population > eighty-pop)
    (unit-type-count transport-ship-class > 0)
=>
    (up-full-reset-search)
    (up-filter-range 5 -1 -1 -1)
    (up-find-local c: transport-ship-class c: 10)
    (up-remove-objects search-local object-data-id g:== transport-exclude-id)
    (up-target-point enemy-x action-unload -1 -1)
)

(defrule
    (timer-triggered ten-mins)
    (unit-type-count transport-ship > 0)
    (population > eighty-pop)
=>
    (up-full-reset-search)
    (up-set-target-point enemy-x)
    (up-filter-include 4 -1 -1 0)
    (up-filter-distance c: -1 c: 50)
    (up-find-local c: all-units-class c: 60)
    (up-target-point 0 action-attack-move -1 -1)
)

;end jump