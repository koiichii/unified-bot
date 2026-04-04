import sys
sys.path.append('/root/unified-bot')

import json
import asyncio
import asyncpg
import config

async def create_table():
    conn = await asyncpg.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    
    # Создаём таблицу (если не существует)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS pokemon_catalog (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            set_name TEXT NOT NULL,
            image TEXT
        )
    ''')
    
    # Очищаем таблицу
    await conn.execute('DELETE FROM pokemon_catalog')
    
    # Загружаем 151 сет (ID 1-187)
    with open('data/pokemon_data.json', 'r', encoding='utf-8') as f:
        for p in json.load(f):
            await conn.execute(
                'INSERT INTO pokemon_catalog (id, name, set_name, image) VALUES ($1, $2, $3, $4)',
                p['id'], p['name'], '151', p.get('image', '')
            )
    
    # Загружаем Prismatic Evolution (ID 188-310)
    next_id = 188
    with open('data/pokemon_data_prisma.json', 'r', encoding='utf-8') as f:
        for p in json.load(f):
            await conn.execute(
                'INSERT INTO pokemon_catalog (id, name, set_name, image) VALUES ($1, $2, $3, $4)',
                next_id, p['name'], 'Prismatic Evolution', p.get('image', '')
            )
            next_id += 1
    
    print(f"✅ Таблица pokemon_catalog создана и заполнена")
    
    count = await conn.fetchval('SELECT COUNT(*) FROM pokemon_catalog')
    print(f"📊 Всего карт: {count}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_table())