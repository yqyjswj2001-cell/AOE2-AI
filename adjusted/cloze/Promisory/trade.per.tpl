(defrule
	(goal escrowing no)
(or	(up-compare-goal cost-wood >= 1)
(or	(up-compare-goal cost-food >= 1)
(or	(up-compare-goal cost-gold >= 1)
	(up-compare-goal cost-stone >= 1))))
=>
;	;(chat-to-player my-player-number "Debugging escrow.t")
	(set-goal cost-wood 0)
	(set-goal cost-food 0)
	(set-goal cost-gold 0)
	(set-goal cost-stone 0)
	(set-goal temporary-goal 48353))
(defrule
	(goal temporary-goal 48353)
=>
	(up-reset-cost-data cost-food)
	(set-escrow-percentage wood 0)
	(set-escrow-percentage food 0)
	(set-escrow-percentage gold 0)
	(set-escrow-percentage stone 0)
	(up-release-escrow)
	(set-goal escrow-flag 0)
	(set-goal escrow-flag2 0))
;================================================================
; Stone excess
;================================================================
(defrule
	(building-type-count-total castle >= {{TRADE_001}})
(or	(goal uugoal no)
	(building-type-count-total castle >= {{TRADE_002}}))
	(building-type-count-total town-center >= {{TRADE_003}})
	(strategic-number sn-military-superiority <= {{TRADE_004}})
	(population < max-civ-pop)
	(military-population < {{TRADE_005}})
	(goal underattack yes)
	(gold-amount < {{TRADE_006}})
	(commodity-selling-price stone >= {{TRADE_007}})
	(can-sell-commodity stone)
=>
	;(chat-local-to-self text-selling-stone)
	(sell-commodity stone))
;================================================================
(defrule
	(up-compare-goal excessStone >= {{TRADE_008}})
(or	(goal uugoal no)
	(up-compare-goal excessStone >= {{TRADE_009}}))
	(gold-amount < {{TRADE_010}})
	(commodity-selling-price stone >= {{TRADE_011}}); 67
	(can-sell-commodity stone)
=>
	;(chat-local-to-self text-selling-stone)
	(sell-commodity stone))
;================================================================
(defrule
	(building-type-count feitoria >= 1)
	(up-compare-goal excessStone >= {{TRADE_013}})
(or	(goal uugoal no)
	(up-compare-goal excessStone >= {{TRADE_014}}))
	(up-compare-goal excessGold < {{TRADE_015}})
	(building-type-count-total castle >= {{TRADE_016}})
(or	(goal uugoal no)
	(building-type-count-total castle >= {{TRADE_017}}))
(or	(strategic-number sn-military-superiority <= -2)
	(population < max-civ-pop))	
	(commodity-selling-price stone >= {{TRADE_018}}); 100
	(can-sell-commodity stone)
=>
	;(chat-local-to-self text-selling-stone)
	(sell-commodity stone))
;================================================================
; Buying stone
;================================================================
#load-if-not-defined WONDER-RACE
(defrule
	(building-type-count-total town-center <= 0)
	(unit-type-count-total villager >= 1)
	(up-compare-goal excessWood >= tc-100-wood)
	(commodity-buying-price stone g:> excessGold)
	(stone-amount < tc-stone)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
(defrule
	(building-type-count-total town-center <= 0)
	(unit-type-count-total villager >= 1)
	(up-compare-goal excessFood >= 100)
(or	(and	(commodity-buying-price wood g:> excessGold)
		(wood-amount < tc-wood))
	(and	(commodity-buying-price stone g:> excessGold)
		(stone-amount < tc-stone)))
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
(defrule
	(building-type-count-total town-center <= 0)
	(unit-type-count-total villager >= 1)
	(up-compare-goal excessStone >= threetc-stone)
	(commodity-buying-price wood g:> excessGold)
	(wood-amount < tc-wood)
	(can-sell-commodity stone)
=>
	;(chat-local-to-self text-selling-stone)
	(sell-commodity stone))
(defrule
	(building-type-count-total town-center <= 0)
	(unit-type-count-total villager >= 1)
(or	(up-compare-goal excessGold >= 400)
(or	(unit-type-count villager-wood <= 0)
	(building-type-count-total lumber-camp <= 0)))
	(wood-amount < 275)
;	(stone-amount >= tc-stone)
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood-town-center)
	(buy-commodity wood))
(defrule
	(building-type-count-total town-center <= 0)
	(unit-type-count-total villager >= 1)
(or	(up-compare-goal excessGold >= 400)
(or	(unit-type-count villager-stone <= 0)
	(building-type-count-total mining-camp <= 0)))
	(wood-amount >= 275)
	(stone-amount < tc-stone)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-town-center)
	(buy-commodity stone))
;================================================================
(defrule
	(goal strategy stonewall)
(or	(up-research-status c: ri-elite-eagle-warrior < research-pending)
	(gold-amount < {{TRADE_034}}))
=>
	(up-jump-rule 10))
(defrule
	(goal strategy fast-imp)
(or	(goal uugoal no)
	(gold-amount < {{TRADE_035}}))
=>
	(up-jump-rule 9))
(defrule
(or	(goal researchplan yes); 180
(or	(goal uugoal yes)
	(unit-type-count villager-stone <= 0))); (strategic-number sn-military-superiority >= 2); 1
;	(goal underattack no)
;	(goal escrowing no)
	(building-type-count-total castle == 0)
	(stone-amount < castle-stone)
	(up-compare-goal excessGold >= {{TRADE_038}})
	(strategic-number sn-current-age >= imperial)
(or	(current-age >= imperial-age)
	(up-compare-goal excessGold >= {{TRADE_039}}))
;	(building-available castle)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-castle)
	(buy-commodity stone)
	(up-jump-rule 1))
(defrule
	(goal uugoal yes)
	(goal underattack no)
	(goal escrowing no)
	(building-type-count-total castle < {{TRADE_040}})
(or	(building-type-count-total castle < 2)
	(up-compare-goal excessGold >= {{TRADE_041}}))
	(stone-amount < castle-stone)
	(up-compare-goal excessGold >= {{TRADE_042}}); 300 in the rule above
	(strategic-number sn-current-age >= imperial)
	(building-available castle)
	(commodity-buying-price stone < {{TRADE_043}})
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-castle)
	(buy-commodity stone)); end mini jump
;================================================================
(defrule
(or	(not	(building-available town-center))
(or	(and	(building-type-count-total town-center >= 3)
		(or	(up-research-status c: ri-bow-saw == research-available)
			(up-research-status c: ri-heavy-plow == research-available)))
	(stone-amount >= tc-stone)))
=>
	(up-jump-rule 4))
(defrule
(or	(building-type-count-total town-center >= 5)
(or	(and	(building-type-count-total town-center >= 4)
		(up-compare-goal milunits != no))
(or	(population >= max-civ-pop)
(or	(civilian-population >= up-max-civ)
(or	(goal underattack yes)
	(unit-type-count villager-stone >= {{TRADE_044}}))))))
=>
	(up-jump-rule 3))
(defrule
(or	(up-compare-goal excessGold >= 1000)
	(strategic-number sn-military-superiority >= {{TRADE_045}}))
(or	(up-compare-goal excessGold >= 1000)
(or	(up-compare-flag escrow-flag2 == 524288); town-center
	(goal dreitc no)))
	(building-type-count-total town-center < {{TRADE_046}})
	(wood-amount >= tc-wood); 315
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-town-center)
	(buy-commodity stone)
	(up-jump-rule 2))
(defrule
(or	(unit-type-count villager-wood >= 28)
(or	(up-compare-goal excessWood >= tc-wood)
(or	(up-compare-flag escrow-flag2 == 524288); town-center
	(building-type-count-total town-center < {{TRADE_047}}))))
(or	(up-compare-flag escrow-flag2 == 524288); town-center
(or	(up-compare-goal milunits <= yes);(or	(goal milunits yes);(or	(goal milunits no)
	(goal dreitc no)));)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-town-center)
	(buy-commodity stone)
	(up-jump-rule 1))
(defrule
(or	(up-compare-goal strategy != stonewall)
	(up-research-status c: ri-elite-eagle-warrior >= research-pending));	(up-research-status c: my-unique-research >= research-pending))
(or	(goal milunits no)
	(and	(building-type-count-total farm g:>= maxfarms)
		(up-research-status c: imperial-age >= research-available))); pending?
(or	(unit-type-count villager-wood >= 28)
(or	(up-compare-goal excessWood >= tc-wood)
	(up-research-status c: ri-heavy-plow >= research-pending)))
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-town-center)
	(buy-commodity stone)); end mini jump
;================================================================
(defrule
	(goal underattack no)
	(strategic-number sn-military-superiority >= {{TRADE_048}})
	(building-type-count-total castle < {{TRADE_049}})
	(stone-amount < castle-stone)
(or	(up-compare-goal excessGold >= 8000)
	(and	(up-compare-goal tradeunits >= 15)
		(up-compare-goal excessGold >= {{TRADE_050}})))
;	(building-available castle)
	(commodity-buying-price stone < {{TRADE_051}})
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-castle)
	(buy-commodity stone))
;================================================================
(defrule
	(goal underattack no)
;	(strategic-number sn-military-superiority >= 0)
	(building-type-count-total castle < {{TRADE_052}})
	(stone-amount < castle-stone)
(or	(up-compare-goal excessGold >= 10200)
	(and	(or	(up-compare-goal tradeunits >= 20)
			(up-compare-goal relic-count >= 3))
		(up-compare-goal excessGold >= {{TRADE_053}})))
;	(building-available castle)
	(commodity-buying-price stone < {{TRADE_054}})
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-castle)
	(buy-commodity stone)); end jump
;================================================================
#load-if-defined VICTORY-STANDARD
(defrule
	(commodity-buying-price stone >= {{TRADE_055}})
	(unit-type-count villager-stone >= {{TRADE_056}})
=>
	(up-jump-rule 2))
;================================================================
(defrule
	(goal wwonder yes)
	(building-type-count-total town-center >= 1)
	(building-type-count-total wonder < 1)
	(players-building-type-count any-ally wonder == 0)
	(wood-amount >= 1100); 1000
	(gold-amount >= 1300)
	(stone-amount < 1000)
	(goal underattack no)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-wonder)
	(buy-commodity stone))
;================================================================
(defrule
	(goal nomaden no)
	(goal landnomad no)
(or	(building-type-count-total wonder >= 1)
	(and	(hold-relics)
		(up-compare-goal relic-count >= 3))); 5
	(wall-completed-percentage 2 < 100)
	(up-compare-goal excessGold >= {{TRADE_063}})
	(stone-amount < 100)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-walls)
	(buy-commodity stone))
#end-if
;================================================================
(defrule
	(goal escrowing no)
	(stone-amount < 125)
	(up-compare-goal excessGold >= {{TRADE_066}})
(or	(up-compare-goal relic-count >= 3)
	(up-compare-goal tradeunits >= 15))
	(commodity-buying-price stone < {{TRADE_067}})
	(building-available bombard-tower)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone)
	(buy-commodity stone))
;================================================================
(defrule
	(goal escrowing no)
	(stone-amount < castle-stone)
	(up-compare-goal excessGold >= {{TRADE_068}})
(or	(up-compare-goal excessGold >= 1000)
(or	(and	(up-compare-goal tradeunits >= 10)
		(commodity-buying-price stone < {{TRADE_069}}))
(or	(up-compare-goal tradeunits >= 30)
	(up-compare-goal relic-count >= 3))))
	(commodity-buying-price stone < {{TRADE_070}})
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone)
	(buy-commodity stone))
;================================================================
(defrule
	(up-compare-goal total-stone-amount g:< cost-stone)
	(unit-type-count villager-stone <= 0)
	(up-compare-goal excessStone <= 0)
	(up-compare-goal excessGold >= 25)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone)
	(buy-commodity stone))
;================================================================
; Food excess
;================================================================
(defrule
	(up-compare-goal excessFood >= {{TRADE_074}})
	(gold-amount < {{TRADE_075}})
(or	(commodity-selling-price food > 35)
	(up-compare-goal excessFood >= {{TRADE_076}}))
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
	(up-compare-goal excessFood >= {{TRADE_077}})
(or	(commodity-selling-price food > 150)
	(up-compare-goal excessFood >= {{TRADE_078}}))
	(gold-amount < {{TRADE_079}})
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
	(up-compare-goal excessFood >= {{TRADE_080}})
	(gold-amount < {{TRADE_081}})
(or	(cc-players-unit-type-count 0 gold-mine < 1)
	(commodity-selling-price food > {{TRADE_082}}))
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
(or	(and	(up-compare-goal excessFood >= 5000)
		(gold-amount < {{TRADE_083}}))
	(and	(up-compare-goal excessFood >= 10000)
		(or	(gold-amount < 2200)
			(game-time < {{TRADE_084}})))); test
(or	(cc-players-unit-type-count 0 gold-mine < 1)
	(commodity-selling-price food > {{TRADE_085}}))
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
	(up-compare-goal excessFood >= {{TRADE_086}})
	(gold-amount < {{TRADE_087}})
	(wood-amount < {{TRADE_088}})
	(cc-players-unit-type-count 0 tree-class < 30)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
	(up-compare-goal excessFood >= {{TRADE_089}})
	(gold-amount < {{TRADE_090}})
	(wood-amount < {{TRADE_091}})
(or	(cc-players-unit-type-count 0 tree-class < 20)
	(dropsite-min-distance wood > 25))
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
(defrule
	(gold-amount g:< cost-gold)
	(unit-type-count villager-gold <= 0)
	(up-compare-goal excessGold <= 0)
	(up-compare-goal excessFood >= 300); 17
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food)
	(sell-commodity food))
;================================================================
; Buying food
;================================================================
(defrule
	(up-compare-goal excessGold >= {{TRADE_095}})
(or	(food-amount < 100)
	(up-compare-goal excessGold >= {{TRADE_096}}))
(or	(food-amount < 200)
	(up-compare-goal excessGold >= {{TRADE_097}}))
	(food-amount < {{TRADE_098}})
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(goal underattack no)
	(food-amount < {{TRADE_099}})
(or	(up-compare-goal excessGold >= 10000)
	(and	(or	(up-compare-goal tradeunits >= 15)
			(up-compare-goal relic-count >= 3))
		(up-compare-goal excessGold >= {{TRADE_100}})))
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(food-amount < {{TRADE_101}})
	(up-compare-goal excessGold >= {{TRADE_102}})
(or	(up-compare-goal relic-count >= 3)
(or	(players-building-type-count any-ally market >= 1)
(or	(players-building-type-count any-ally port >= 1)
	(players-building-type-count any-ally dock >= 1))))
(or	(up-compare-goal relic-count >= 3)
	(up-compare-goal tradeunits >= 15))
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(goal escrowing no)
	(food-amount < {{TRADE_104}})
	(up-compare-goal excessGold >= {{TRADE_105}})
(or	(and	(up-compare-goal tradeunits >= 10)
		(commodity-buying-price food < {{TRADE_106}}))
(or	(up-compare-goal tradeunits >= 30)
	(up-compare-goal relic-count >= 3)))
	(commodity-buying-price food < {{TRADE_107}})
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(up-compare-goal total-food-amount g:< cost-food)
	(unit-type-count villager-food <= 0)
	(up-compare-goal excessFood <= 0)
	(up-compare-goal excessGold >= 25)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(up-train-site-ready c: villager)
	(up-compare-goal excessFood < vill-cost)
(or	(goal escrow-state without-escrow)
	(up-compare-goal total-food-amount < vill-cost))
	(up-compare-goal custom-civ-pop < min-number-vills)
(or	(up-compare-goal tradeunits >= 12)
(or	(up-compare-goal relic-count >= 3)
	(up-compare-goal excessGold >= 900)))
	(goal underattack no)
	(goal defend no)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
(defrule
	(up-train-site-ready c: villager)
	(up-compare-goal excessFood < vill-cost)
	(building-type-count town-center >= 1)
	(unit-type-count-total villager <= 1)
	(goal underattack no)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food)
	(buy-commodity food))
;================================================================
; Wood excess
;================================================================
(defrule
(or	(cc-players-unit-type-count 0 tree-class > 150)
	(dropsite-min-distance wood < 5))
(or	(cc-players-unit-type-count 0 tree-class > 300)
	(dropsite-min-distance wood < 10))
	(up-compare-goal excessWood >= {{TRADE_114}})
	(gold-amount < {{TRADE_115}})
(or	(commodity-selling-price wood > 35)
	(up-compare-goal excessWood >= {{TRADE_116}}))
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
(or	(cc-players-unit-type-count 0 tree-class > 150)
	(dropsite-min-distance wood < 5))
(or	(cc-players-unit-type-count 0 tree-class > 300)
	(dropsite-min-distance wood < 10))
(or	(up-compare-goal excessWood >= 1100)
	(commodity-selling-price wood > {{TRADE_117}}))
	(up-compare-goal excessWood >= {{TRADE_118}})
	(gold-amount < {{TRADE_119}})
	(commodity-selling-price wood > {{TRADE_120}})
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
(or	(cc-players-unit-type-count 0 tree-class > 150)
	(dropsite-min-distance wood < 5))
(or	(cc-players-unit-type-count 0 tree-class > 300)
	(dropsite-min-distance wood < 10))
	(up-compare-goal excessWood >= {{TRADE_121}})
	(gold-amount < {{TRADE_122}})
(or	(cc-players-unit-type-count 0 gold-mine < 1)
	(commodity-selling-price wood > {{TRADE_123}}))
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
(or	(cc-players-unit-type-count 0 tree-class > 150)
	(dropsite-min-distance wood < 5))
(or	(cc-players-unit-type-count 0 tree-class > 300)
	(dropsite-min-distance wood < 10))
	(up-compare-goal excessWood >= {{TRADE_124}})
(or	(gold-amount < 2200)
	(game-time < {{TRADE_125}})); test
(or	(cc-players-unit-type-count 0 gold-mine < 1)
	(commodity-selling-price wood > {{TRADE_126}}))
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
(or	(cc-players-unit-type-count 0 tree-class > 150)
	(dropsite-min-distance wood < 5))
(or	(cc-players-unit-type-count 0 tree-class > 300)
	(dropsite-min-distance wood < 10))
	(up-compare-goal excessWood >= {{TRADE_127}})
	(food-amount < {{TRADE_128}})
	(gold-amount < {{TRADE_129}})
	(population < max-civ-pop)
	(civilian-population < up-max-civ)
;(or	(cc-players-unit-type-count 0 gold-mine < 1)
;	(commodity-selling-price wood > 45))
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
	(building-type-count-total town-center < {{TRADE_130}})
	(up-compare-goal custom-civ-pop < up-max-civ)
	(population < max-civ-pop)
	(building-available town-center)
	(stone-amount < tc-stone)
	(up-compare-goal excessWood >= tc-100-wood)
	(gold-amount < {{TRADE_131}})
	(up-compare-goal excessFood >= {{TRADE_132}})
	(unit-type-count villager-stone <= {{TRADE_133}})
(or	(up-compare-goal excessWood >= 700)
	(commodity-buying-price stone < {{TRADE_134}}))
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
(defrule
	(gold-amount g:< cost-gold)
	(unit-type-count villager-gold <= 0)
	(up-compare-goal excessGold <= 0)
	(up-compare-goal excessWood >= 300); 17
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood)
	(sell-commodity wood))
;================================================================
; Buying wood
;================================================================
(defrule
(or	(and	(gold-amount < castle-gs)
		(research-available castle-age))
	(and	(gold-amount < imperial-gs)
		(research-available imperial-age)))
=>
	(up-jump-rule 6))
;================================================================
;(defrule
;	(wood-amount < 60)
;(or	(cc-players-unit-type-count 0 tree-class < 175)
;	(dropsite-min-distance wood > 20))
;	(can-buy-commodity wood)
;=>
;	;(chat-local-to-self text-buying-wood)
;	(buy-commodity wood))
;================================================================
(defrule
	(wood-amount < {{TRADE_138}})
; hm	(up-compare-goal excessGold >= 100)
(or	(cc-players-unit-type-count 0 tree-class < 175)
	(dropsite-min-distance wood > 20))
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
(defrule
	(wood-amount < {{TRADE_139}})
(or	(and	(up-compare-goal excessGold >= 300)
		(or	(cc-players-unit-type-count 0 tree-class < 175)
			(dropsite-min-distance wood > 20)))
(or	(up-compare-goal excessGold >= 1600)
	(up-compare-goal excessFood >= {{TRADE_140}}))); sell food instead
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
;(defrule
;	(wood-amount < 200)
;	(up-compare-goal excessGold >= 700)
;	(can-buy-commodity wood)
;=>
;	;(chat-local-to-self text-buying-wood)
;	(buy-commodity wood))
;================================================================
;(defrule
;	(wood-amount < 300)
;	(up-compare-goal excessGold >= 1200)
;	(can-buy-commodity wood)
;=>
;	;(chat-local-to-self text-buying-wood)
;	(buy-commodity wood))
;================================================================
(defrule
	(goal underattack no)
	(wood-amount < {{TRADE_141}})
(or	(up-compare-goal excessGold >= 10000)
	(and	(or	(up-compare-goal tradeunits >= 15)
			(up-compare-goal relic-count >= 3))
		(up-compare-goal excessGold >= {{TRADE_142}})))
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
(defrule
	(wood-amount < {{TRADE_143}})
	(up-compare-goal excessGold >= {{TRADE_144}})
(or	(up-compare-goal relic-count >= 3)
(or	(players-building-type-count any-ally market >= 1)
(or	(players-building-type-count any-ally port >= 1)
	(players-building-type-count any-ally dock >= 1))))
(or	(up-compare-goal relic-count >= 3)
	(up-compare-goal tradeunits >= 15))
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
(defrule
	(goal escrowing no)
	(wood-amount < {{TRADE_146}})
	(up-compare-goal excessGold >= {{TRADE_147}})
(or	(and	(up-compare-goal tradeunits >= 10)
		(commodity-buying-price wood < {{TRADE_148}}))
(or	(up-compare-goal tradeunits >= 30)
	(up-compare-goal relic-count >= 3)))
	(commodity-buying-price wood < {{TRADE_149}})
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
(defrule
	(unit-type-count villager <= 0)
	(building-type-count town-center <= 0)
	(building-type-count market >= 1)
	(player-in-game any-ally)
	(players-building-type-count any-ally market >= 1)
	(wood-amount < 100)
; nn	(up-compare-goal excessGold >= 300);
	(housing-headroom >= 1)
	(unit-type-count-total 178 <= 0); Dead trade cart (empty)
	(unit-type-count-total 205 <= 0); Dead trade cart (full)
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood)); end jump
;================================================================
(defrule
	(wood-amount g:< cost-wood)
	(unit-type-count villager-wood <= 0)
	(up-compare-goal excessWood <= 0)
	(up-compare-goal excessGold >= 25)
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood)
	(buy-commodity wood))
;================================================================
; Trading to accomplish important goals
;================================================================
(defrule
;	(strategic-number sn-current-age == dark)
	(building-type-count town-center >= 1)
	(up-compare-goal total-food-amount < feudal-food)
	(research-available feudal-age)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food-next-age)
	(buy-commodity food))
;================================================================
(defrule
;	(strategic-number sn-current-age == feudal)
	(building-type-count town-center >= 1)
;	(building-type-count blacksmith >= 1)
	(up-compare-goal total-food-amount < castle-food)
	(gold-amount >= castle-gs)
	(research-available castle-age)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food-next-age)
	(buy-commodity food))
;================================================================
(defrule
;	(strategic-number sn-current-age == feudal)
	(building-type-count town-center >= 1)
;	(building-type-count blacksmith >= 1)
	(gold-amount < castle-gold)
	(up-compare-goal total-food-amount >= castle-fs)
	(research-available castle-age)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-next-age)
	(sell-commodity food))
;================================================================
(defrule
;	(strategic-number sn-current-age == feudal)
	(building-type-count town-center >= 1)
;	(building-type-count blacksmith >= 1)
(or	(up-compare-goal total-food-amount >= castle-f2)
	(wood-amount >= {{TRADE_164}})); test
(or	(gold-amount < castle-gold)
	(up-compare-goal total-food-amount < castle-food))
	(wood-amount >= 100)
	(research-available castle-age)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-next-age)
	(sell-commodity wood))
;================================================================
(defrule
;	(goal underattack no)
;	(strategic-number sn-current-age == castlea)
	(building-type-count town-center >= 1)
;	(goal dreitc yes)
(or	(goal strategy fast-imp)
(or	(population >= up-max-civ)
(or	(up-compare-goal custom-civ-pop >= up-max-civ)
	(up-compare-flag escrow-flag == 2))))
	(food-amount >= imperial-fs)
	(gold-amount < imperial-gold)
	(research-available imperial-age)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-next-age)
	(sell-commodity food))
;================================================================
(defrule
;	(goal underattack no)
;	(strategic-number sn-current-age == castlea)
	(building-type-count town-center >= 1)
;	(goal dreitc yes)
(or	(goal strategy fast-imp)
(or	(population >= up-max-civ)
(or	(up-compare-goal custom-civ-pop >= up-max-civ)
	(up-compare-flag escrow-flag == 2))))
	(food-amount < imperial-food); 901
	(gold-amount >= imperial-gs)
	(research-available imperial-age)
	(can-buy-commodity food)
;(or
;	(up-research-status c: ri-hand-cart >= research-pending)
;	(wood-amount <= 100))
=>
	;(chat-local-to-self text-buying-food-next-age)
	(buy-commodity food))
;================================================================
(defrule
;	(goal underattack no)
;	(strategic-number sn-current-age == castlea)
	(building-type-count town-center >= 1)
;	(goal dreitc yes)
(or	(goal strategy fast-imp)
(or	(population >= up-max-civ)
(or	(up-compare-goal custom-civ-pop >= up-max-civ)
	(up-compare-flag escrow-flag == 2))))
;	(food-amount < imperial-food)
	(gold-amount < imperial-gold)
	(wood-amount >= 100); 300
	(research-available imperial-age)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-next-age)
	(sell-commodity wood))
;================================================================
(defrule
	(research-available imperial-age)
(or	(food-amount < imperial-food)
	(gold-amount < imperial-gold))
(or	(goal strategy fast-imp)
	(up-compare-flag escrow-flag == 2))
	(gold-amount < {{TRADE_170}})
	(goal underattack no)
	(building-type-count town-center >= 1)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-next-age)
	(sell-commodity wood))
;================================================================
(defrule
	(research-available imperial-age)
(or	(food-amount < imperial-food)
	(gold-amount < imperial-gold))
	(up-compare-goal excessWood >= {{TRADE_172}})
(or	(and	(gold-amount < imperial-gs)
		(commodity-selling-price wood >= {{TRADE_173}}))
	(up-compare-goal excessWood >= {{TRADE_174}}))
	(gold-amount < {{TRADE_175}})
	(goal underattack no)
	(building-type-count town-center >= 1)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-next-age)
	(sell-commodity wood))
;================================================================
(defrule
(or	(and	(up-compare-goal escrowing != no)
		(and	(up-compare-flag escrow-flag != 4)
			(and	(up-compare-flag escrow-flag != 32768)
				(up-compare-flag escrow-flag != 4096))))
	(goal underattack yes))
=>
	(up-jump-rule 10))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total my-unique-unit-line >= 8)
	(goal uugoal yes))
	(population >= up-max-civ)
	(gold-amount < uu-gold)
	(food-amount > uu-food)
	(food-amount >= {{TRADE_177}})
(or	(commodity-selling-price food > 23)
	(food-amount >= {{TRADE_178}}))
	(current-age >= imperial-age)
	(building-type-count castle >= 1)
	(up-research-status c: my-unique-unit-upgrade < research-pending)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-elite-X)
	(sell-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total my-unique-unit-line >= 8)
	(goal uugoal yes))
	(population >= up-max-civ)
	(gold-amount > uu-gold2)
	(food-amount < uu-food2)
(or	(commodity-buying-price food < 150)
	(gold-amount >= {{TRADE_180}}))
	(current-age >= imperial-age)
	(building-type-count castle >= 1)
	(up-research-status c: my-unique-unit-upgrade < research-pending)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food-elite-X)
	(buy-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total my-unique-unit-line >= 8)
	(goal uugoal yes))
	(population >= up-max-civ)
	(gold-amount < uu-gold)
	(wood-amount > uu-wood)
	(wood-amount >= {{TRADE_182}})
(or	(commodity-selling-price wood > 23)
	(wood-amount >= {{TRADE_183}}))
	(current-age >= imperial-age)
	(building-type-count castle >= 1)
	(up-research-status c: my-unique-unit-upgrade < research-pending)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-elite-X)
	(sell-commodity wood))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total my-unique-unit-line >= 8)
	(goal uugoal yes))
	(population >= up-max-civ)
	(gold-amount > uu-gold2)
	(wood-amount < uu-wood2)
(or	(commodity-buying-price wood < 150)
	(gold-amount >= {{TRADE_185}}))
	(current-age >= imperial-age)
	(building-type-count castle >= 1)
	(up-research-status c: my-unique-unit-upgrade < research-pending)
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood-elite-X)
	(buy-commodity wood))
;================================================================
(defrule
; j	(goal underattack no)
(or	(and	(unit-type-count-total knight-line >= 18)
		(up-research-status c: ri-bloodlines >= research-pending))
	(goal palagoal yes))
	(gold-amount < 750)
	(food-amount >= 1400)
	(research-completed ri-cavalier)
	(up-research-status c: ri-plate-barding >= research-pending)
	(research-available ri-paladin)
	(building-type-count stable >= 1)
	(up-research-status c: ri-paladin < research-pending)
	(current-age >= imperial-age)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-palas)
	(sell-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(and	(unit-type-count-total knight-line >= 18)
		(up-research-status c: ri-bloodlines >= research-pending))
	(goal palagoal yes))
	(gold-amount >= 950); 900
	(food-amount < 1300)
	(research-completed ri-cavalier)
	(up-research-status c: ri-plate-barding >= research-pending)
	(research-available ri-paladin)
	(building-type-count stable >= 1)
	(up-research-status c: ri-paladin < research-pending)
	(current-age >= imperial-age)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food-palas)
	(buy-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(and	(unit-type-count-total knight-line >= 18)
		(up-research-status c: ri-bloodlines >= research-pending))
	(goal palagoal yes))
	(research-completed ri-cavalier)
	(up-research-status c: ri-plate-barding >= research-pending)
	(research-available ri-paladin)
	(building-type-count stable >= 1)
	(up-research-status c: ri-paladin < research-pending)
	(food-amount >= 800)
	(gold-amount < 750)
	(wood-amount >= {{TRADE_196}})
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-palas)
	(sell-commodity wood))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total two-handed-swordsman >= 5)
	(goal champgoal yes))
	(gold-amount < 350)
	(food-amount >= 850)
	(research-completed ri-two-handed-swordsman)
	(up-research-status c: ri-scale-mail >= research-pending); for now
	(research-available ri-champion)
	(building-type-count barracks >= 1)
	(up-research-status c: ri-champion < research-pending)
	(current-age >= imperial-age)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-champs)
	(sell-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total two-handed-swordsman >= 5)
	(goal champgoal yes))
	(gold-amount >= 550); 500
	(food-amount < 750)
	(research-completed ri-two-handed-swordsman)
	(up-research-status c: ri-scale-mail >= research-pending); for now
	(research-available ri-champion)
	(building-type-count barracks >= 1)
	(up-research-status c: ri-champion < research-pending)
	(current-age >= imperial-age)
	(can-buy-commodity food)
=>
	;(chat-local-to-self text-buying-food-champs)
	(buy-commodity food))
;================================================================
(defrule
; j	(goal underattack no)
(or	(unit-type-count-total two-handed-swordsman >= 5)
	(goal champgoal yes))
	(current-age >= imperial-age)
	(research-completed ri-two-handed-swordsman)
	(up-research-status c: ri-scale-mail >= research-pending); for now
	(research-available ri-champion)
	(building-type-count barracks >= 1)
	(up-research-status c: ri-champion < research-pending)
	(food-amount >= 450)
	(gold-amount < 350)
	(wood-amount >= {{TRADE_206}})
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-champs)
	(sell-commodity wood))
#else; WR
(defrule
	(gold-amount >= 1200)
	(stone-amount < 1000)
	(current-age >= imperial-age)
	(can-buy-commodity stone)
=>
	;(chat-local-to-self text-buying-stone-wonder)
	(buy-commodity stone))
(defrule
(or	(gold-amount < 1000)
	(wood-amount < 1000))
	(stone-amount >= 1100)
	(current-age >= imperial-age)
	(can-sell-commodity stone)
=>
	;(chat-local-to-self text-selling-stone-wonder)
	(sell-commodity stone))
(defrule
	(gold-amount >= 1200)
	(wood-amount < 1000)
	(current-age >= imperial-age)
	(can-buy-commodity wood)
=>
	;(chat-local-to-self text-buying-wood-wonder)
	(buy-commodity wood))
(defrule
(or	(gold-amount < 1000)
	(stone-amount < 1000))
	(wood-amount >= 1100)
	(current-age >= imperial-age)
	(can-sell-commodity wood)
=>
	;(chat-local-to-self text-selling-wood-wonder)
	(sell-commodity wood))
(defrule
	(food-amount >= 100)
(or	(building-available wonder)
	(food-amount >= 200))
	(current-age >= imperial-age)
	(can-sell-commodity food)
=>
	;(chat-local-to-self text-selling-food-wonder)
	(sell-commodity food))
#end-if
;If being slung take more agressive steps to imp fast - it's unlikely with human/other ai resource coordination will be perfect
#load-if-defined COMMENT-OUT
(defrule
	(or(players-tribute-memory every-ally food < 400)
	(game-time > 1800))
=>
	(up-jump-rule 4);for peformance reasons
)

#end-if

(defrule
	(up-research-status c: imperial-age < research-pending)
	(food-amount > 1150)
	(gold-amount < 800)
	(can-buy-commodity gold)
	(current-age == castle-age)
	(game-time < 1700)
;	(players-tribute-memory any-ally food > 500)
	(can-sell-commodity food)
=>
	(sell-commodity food)
	(chat-local-to-self "sell food")
)

(defrule
	(up-research-status c: imperial-age < research-pending)
	(gold-amount > 950)
	(food-amount < 1000)
	(can-buy-commodity food)
;	(players-tribute-memory any-ally food > 500)
;	(players-tribute-memory any-ally gold > 100)
	(game-time < {{TRADE_223}})
	(current-age == castle-age)
	(can-buy-commodity food)
=>
	(buy-commodity food)
	
	(chat-local-to-self "Debug: buying food")
)


(defrule
;	(nand(building-type-count-total monastery > 0)
;	(building-type-count-total siege-workshop > 0));
;	(nand(building-type-count-total siege-workshop > 0)
;	(building-type-count-total university > 0))
;	(nand(building-type-count-total university > 0)
;	(building-type-count-total monastery > 0))
	(building-type-count-total castle < 1)
;	(players-tribute-memory any-ally food > 500)
	(game-time < {{TRADE_225}})
	(wood-amount < 250)
	(can-buy-commodity wood)
	(gold-amount > 950)
	(current-age == castle-age)
;	(up-research-status c: imperial-age < status-pending)
=>
	(buy-commodity wood)
	(chat-local-to-self "Debug: buying wood")
)

(defrule
	(building-type-count-total monastery < 1)
	(or(building-type-count-total siege-workshop < 1)
	(building-type-count-total university < 1))
	(gold-amount > 1100)
	(can-buy-commodity stone)
	(stone-amount < 650)
	(building-type-count-total castle < 1)
=>
	(buy-commodity stone)
)
(defrule
	(food-amount > 1100)
	(or(gold-amount < 800)
	(and(food-amount > 1300)
	(gold-amount < 1000)))
	(can-sell-commodity food)
;	(players-tribute-memory any-ally food > 500)
	(game-time < {{TRADE_235}})
	(can-sell-commodity food)
	(current-age == castle-age)
	(up-research-status c: imperial-age < status-pending)
=>
	(sell-commodity food)
	(chat-local-to-self "Debug: selling food")
)

(defrule
	(research-completed ri-elite-eagle-warrior)
	(unit-type-count-total eagle-warrior-line > {{TRADE_236}})
	(building-type-count-total castle < 1)
	(not(research-completed my-unique-research))
	(gold-amount > 900)
	(stone-amount < 650)
	(can-buy-commodity stone)
=>
	(buy-commodity stone)
)

(defrule
	(can-buy-commodity food)
	(commodity-buying-price food < {{TRADE_240}})
	(goal strategy krush)
	(unit-type-count-total villager < {{TRADE_241}})
	(gold-amount > {{TRADE_242}})
	(food-amount < {{TRADE_243}})
	(current-age == castle-age)
	(current-age-time < {{TRADE_244}})
=>
	(buy-commodity food)
)

;----------------------------
; Merchant Ship Ratio Swap
;----------------------------  
(defrule
	(up-gaia-type-count-total c: wood >= 30)
	(gold-amount <= 1500)
    (unit-type-count-total merchant-ship > 0)
    (or (up-research-status c: ri-merchant-ratio-wood >= research-complete)
        (up-research-status c: ri-merchant-ratio-gold >= research-complete))
	(can-research ri-merchant-ratio-gold)
=>
	(research ri-merchant-ratio-gold)
	(up-jump-rule 7))

(defrule
	(up-gaia-type-count-total c: wood >= 30)
	(gold-amount <= 1500)
    (unit-type-count-total merchant-ship > 0)
    (up-research-status c: ri-merchant-ratio-balanced >= research-complete)
	(can-research ri-merchant-ratio-wood)
=>
    (research ri-merchant-ratio-wood)
    (up-jump-rule -1))
	
(defrule
	(up-gaia-type-count-total c: wood >= 30)
	(wood-amount > 1000)
	(wood-amount < 3000)
	(gold-amount > 1500)
    (unit-type-count-total merchant-ship > 0)
    (or (up-research-status c: ri-merchant-ratio-gold >= research-complete)
        (up-research-status c: ri-merchant-ratio-balanced >= research-complete))
	(can-research ri-merchant-ratio-balanced)
=>
	(research ri-merchant-ratio-balanced)
	(up-jump-rule 5))

(defrule
	(up-gaia-type-count-total c: wood >= 30)
	(wood-amount > 1000)
	(wood-amount < 3000)
	(gold-amount > 1500)
    (unit-type-count-total merchant-ship > 0)
    (up-research-status c: ri-merchant-ratio-wood >= research-complete)
	(can-research ri-merchant-ratio-gold)
=>
    (research ri-merchant-ratio-gold)
    (up-jump-rule -1))

(defrule ;low on wood
	(up-gaia-type-count-total c: wood >= 30)
	(wood-amount <= 500)
	(gold-amount > 1500)
    (unit-type-count-total merchant-ship > 0)
    (or (up-research-status c: ri-merchant-ratio-balanced >= research-complete)
        (up-research-status c: ri-merchant-ratio-wood >= research-complete))
	(can-research ri-merchant-ratio-wood)
=>
	(research ri-merchant-ratio-wood)
	(up-jump-rule 3))

(defrule
	(up-gaia-type-count-total c: wood >= 30)
	(wood-amount <= 500)
	(gold-amount > 1500)
    (unit-type-count-total merchant-ship > 0)
    (up-research-status c: ri-merchant-ratio-gold >= research-complete)
	(can-research ri-merchant-ratio-balanced)
=>
    (research ri-merchant-ratio-balanced)
    (up-jump-rule -1))

	(defrule ;wood starvation
	(up-gaia-type-count-total c: wood < 30)
	(wood-amount < 1000)
	(unit-type-count-total merchant-ship > 0)
    (or (up-research-status c: ri-merchant-ratio-balanced >= research-complete)
        (up-research-status c: ri-merchant-ratio-wood >= research-complete))
	(can-research ri-merchant-ratio-wood)
=>
	(research ri-merchant-ratio-wood)
    (up-jump-rule 1))

(defrule
	(up-gaia-type-count-total c: wood < 30)
	(wood-amount < 1000)
	(unit-type-count-total merchant-ship > 0)
    (up-research-status c: ri-merchant-ratio-gold >= research-complete)
	(can-research ri-merchant-ratio-balanced)
=>
    (research ri-merchant-ratio-balanced)
    (up-jump-rule -1))