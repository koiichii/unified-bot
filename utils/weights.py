# utils/weights.py
import random
import json
import math

# Загружаем JSON
with open('data/pokemon_data.json', 'r', encoding='utf-8') as f:
    POKEMON_DB_151 = json.load(f)

with open('data/pokemon_data_prisma.json', 'r', encoding='utf-8') as f:
    POKEMON_DB_PRISMA = json.load(f)

def calculate_normal_weights(pokemon_list):
    weights = []
    desired_contribution = 0.5
    
    for p in pokemon_list:
        price = p["price"]
        if p["rarity"] in ["Rare", "Double_rare", "Ultra_rare", 
                           "Illustration_rare", "Special_illustration_rare", 
                           "Hyper_rare"]:
            weight = (desired_contribution / price) * 0.4
        else:
            weight = desired_contribution / price
        weights.append(max(weight, 0.000001))
    
    return weights

def calculate_normal_weights_151(pokemon_list):
    weights = []
    desired_contribution = 0.5
    
    for p in pokemon_list:
        price = p["price"]
        if p["rarity"] in ["Rare", "Double_rare", "Ultra_rare", 
                           "Illustration_rare", "Special_illustration_rare", 
                           "Hyper_rare"]:
            weight = (desired_contribution / price) * 0.20
        else:
            weight = desired_contribution / price
        weights.append(max(weight, 0.000001))

    return weights 

def get_guaranteed_card_151(pokemon_list):
    rare_plus = [p for p in pokemon_list 
                 if p["rarity"] in ["Rare", "Double_rare", "Ultra_rare", 
                                    "Illustration_rare", "Special_illustration_rare", 
                                    "Hyper_rare"]]
    
    if not rare_plus:
        return random.choice(pokemon_list)
    
    weights = [1 / (p["price"] ** 0.75) for p in rare_plus] 
    return random.choices(rare_plus, weights=weights, k=1)[0]

def get_guaranteed_card(pokemon_list):
    rare_plus = [p for p in pokemon_list 
                 if p["rarity"] in ["Rare", "Double_rare", "Ultra_rare", 
                                    "Illustration_rare", "Special_illustration_rare", 
                                    "Hyper_rare"]]
    
    if not rare_plus:
        return random.choice(pokemon_list)
    
    weights = [1 / (p["price"] ** 0.32) for p in rare_plus]
    return random.choices(rare_plus, weights=weights, k=1)[0]

def open_pack(pokemon_list, normal_weights):
    pack = []
    
    for _ in range(9):
        pack.append(random.choices(pokemon_list, weights=normal_weights, k=1)[0])
    
    pack.append(get_guaranteed_card(pokemon_list))
    
    return pack

def open_pack_151(pokemon_list, normal_weights):
    """Специальная функция для 151 сета"""
    pack = []
    
    for _ in range(9):
        pack.append(random.choices(pokemon_list, weights=normal_weights, k=1)[0])
    
    pack.append(get_guaranteed_card_151(pokemon_list))
    return pack

# Предрасчет весов
NORMAL_WEIGHTS_151 = calculate_normal_weights_151(POKEMON_DB_151)
NORMAL_WEIGHTS_PRISMA = calculate_normal_weights(POKEMON_DB_PRISMA)