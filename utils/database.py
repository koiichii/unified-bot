import asyncio
import asyncpg
import config
from utils.prices import get_pokemon_price_by_id

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            print("DEBUG: Создание пула подключений...")
            self.pool = await asyncpg.create_pool(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                timeout=10
            )
            print("Подключено к базе данных SpaceWeb")
        except Exception as e:
            print(f"Ошибка подключения: {e}")

    async def get_user(self, user_id: int, guild_id: int):
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT * FROM user_data WHERE user_id = $1 AND guild_id = $2',
                user_id, guild_id
            )
            if user:
                return dict(user)
            await conn.execute("""
                INSERT INTO user_data (user_id, guild_id, username, level, xp, xp_to_next_level, messages_count, voice_minutes, money, roles)
                VALUES ($1, $2, $3, 1, 0, 100, 0, 0, 0, $4)
            """, user_id, guild_id, str(user_id), [])
            return {'user_id': user_id, 'guild_id': guild_id, 'money': 0, 'level': 1, 'xp': 0}

    async def update_user_money(self, user_id: int, guild_id: int, amount: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                'UPDATE user_data SET money = money + $1 WHERE user_id = $2 AND guild_id = $3',
                amount, user_id, guild_id
            )

    async def get_user_collection(self, user_id: int):
        async with self.pool.acquire() as conn:
            pokemons = await conn.fetch(
                'SELECT pokemon_id, source, grade FROM user_pokemons WHERE user_id = $1',
                user_id
            )
            duplicates = await conn.fetch(
                'SELECT pokemon_id, source, grade FROM user_duplicates WHERE user_id = $1',
                user_id
            )
            return {
                "pokemons": [dict(p) for p in pokemons],
                "duplicates": [dict(d) for d in duplicates],
                "total_caught": len(pokemons) + len(duplicates)
            }

    async def add_pokemon_to_collection(self, user_id: int, pokemon_id: int, source: str, grade: int = 0):
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval(
                'SELECT id FROM user_pokemons WHERE user_id = $1 AND pokemon_id = $2',
                user_id, pokemon_id
            )
            if existing:
                await conn.execute(
                    'INSERT INTO user_duplicates (user_id, pokemon_id, source, grade) VALUES ($1, $2, $3, $4)',
                    user_id, pokemon_id, source, grade
                )
            else:
                await conn.execute(
                    'INSERT INTO user_pokemons (user_id, pokemon_id, source, grade) VALUES ($1, $2, $3, $4)',
                    user_id, pokemon_id, source, grade
                )

    async def sell_all_duplicates(self, user_id: int):
        async with self.pool.acquire() as conn:
            duplicates = await conn.fetch(
                'SELECT pokemon_id FROM user_duplicates WHERE user_id = $1',
                user_id
            )
            if not duplicates:
                return 0
            total_price = 0
            for dup in duplicates:
                price = get_pokemon_price_by_id(dup['pokemon_id'])
                total_price += price
            await conn.execute('DELETE FROM user_duplicates WHERE user_id = $1', user_id)
            return total_price

# Создаём глобальный экземпляр
db = Database()