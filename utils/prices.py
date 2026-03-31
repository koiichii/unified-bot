from utils.weights import POKEMON_DB_151, POKEMON_DB_PRISMA

# Создаём словарь для быстрого поиска цены по ID
PRICE_CACHE = {}

for pokemon in POKEMON_DB_151:
    PRICE_CACHE[pokemon['id']] = pokemon['price']

for pokemon in POKEMON_DB_PRISMA:
    PRICE_CACHE[pokemon['id']] = pokemon['price']

def get_pokemon_price_by_id(pokemon_id: int) -> float:
    return PRICE_CACHE.get(pokemon_id, 0.0)