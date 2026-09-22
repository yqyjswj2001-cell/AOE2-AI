; CLOZE TEMPLATE - three sell and three buy rules, one per non-gold resource
(defrule
    (building-type-count-total market >= 1)
    (food-amount > {{SELL_FOOD_STOCK_ABOVE}})
    (gold-amount < {{MARKET_GOLD_FLOOR}})
    (commodity-selling-price food >= {{SELL_FOOD_MIN_PRICE}})
    (can-sell-commodity food)
=>
    (sell-commodity food)
)
(defrule
    (building-type-count-total market >= 1)
    (wood-amount > {{SELL_WOOD_STOCK_ABOVE}})
    (gold-amount < {{MARKET_GOLD_FLOOR}})
    (commodity-selling-price wood >= {{SELL_WOOD_MIN_PRICE}})
    (can-sell-commodity wood)
=>
    (sell-commodity wood)
)
(defrule
    (building-type-count-total market >= 1)
    (stone-amount > {{SELL_STONE_STOCK_ABOVE}})
    (gold-amount < {{MARKET_GOLD_FLOOR}})
    (commodity-selling-price stone >= {{SELL_STONE_MIN_PRICE}})
    (can-sell-commodity stone)
=>
    (sell-commodity stone)
)
(defrule
    (building-type-count-total market >= 1)
    (food-amount < {{BUY_FOOD_STOCK_BELOW}})
    (gold-amount > {{BUY_FOOD_GOLD_ABOVE}})
    (commodity-buying-price food <= {{BUY_FOOD_MAX_PRICE}})
    (can-buy-commodity food)
=>
    (buy-commodity food)
)
(defrule
    (building-type-count-total market >= 1)
    (wood-amount < {{BUY_WOOD_STOCK_BELOW}})
    (gold-amount > {{BUY_WOOD_GOLD_ABOVE}})
    (commodity-buying-price wood <= {{BUY_WOOD_MAX_PRICE}})
    (can-buy-commodity wood)
=>
    (buy-commodity wood)
)
(defrule
    (building-type-count-total market >= 1)
    (stone-amount < {{BUY_STONE_STOCK_BELOW}})
    (gold-amount > {{BUY_STONE_GOLD_ABOVE}})
    (commodity-buying-price stone <= {{BUY_STONE_MAX_PRICE}})
    (can-buy-commodity stone)
=>
    (buy-commodity stone)
)
