# utils/album_renderer.py
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from utils.album_layout import (
    ALBUM_WIDTH, ALBUM_HEIGHT, ALBUM_BACKGROUND,
    CARD_WIDTH, CARD_HEIGHT, get_slots_for_page
)

async def get_card_image_by_id(pokemon_id: int, set_name: str):
    """Получает URL изображения карты по её ID"""
    from utils.weights import POKEMON_DB_151, POKEMON_DB_PRISMA
    
    if set_name == "151":
        for p in POKEMON_DB_151:
            if p['id'] == pokemon_id:
                return p.get('image')
    else:
        for p in POKEMON_DB_PRISMA:
            if p['id'] == pokemon_id:
                return p.get('image')
    return None

async def create_album_page(user_id: int, set_name: str, page_number: int, user_cards: dict):
    """
    Создаёт страницу альбома
    
    Args:
        user_id: ID пользователя (не используется, но оставлено для совместимости)
        set_name: "151" или "prismatic"
        page_number: номер страницы (1, 2, 3...)
        user_cards: словарь {pokemon_id: карта} для быстрого доступа
    
    Returns:
        BytesIO с изображением страницы альбома
    """
    # Открываем фон
    background = Image.open(ALBUM_BACKGROUND)
    background = background.resize((ALBUM_WIDTH, ALBUM_HEIGHT))
    
    # Создаём слой для рисования
    draw = ImageDraw.Draw(background)
    
    # Загружаем шрифт (опционально)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 16)
        except:
            font = ImageFont.load_default()
    
    # Определяем диапазон ID для этой страницы
    start_id = (page_number - 1) * 6 + 1
    end_id = start_id + 5
    
    # Получаем слоты для этой страницы
    slots = get_slots_for_page(page_number, start_id)
    
    async with aiohttp.ClientSession() as session:
        for pokemon_id, slot in slots.items():
            x, y = slot["x"], slot["y"]
            
            # Рисуем рамку слота
            draw.rectangle(
                [x, y, x + CARD_WIDTH, y + CARD_HEIGHT],
                outline=(180, 180, 180),
                width=2
            )
            
            # Если у пользователя есть эта карта
            if pokemon_id in user_cards:
                card = user_cards[pokemon_id]
                image_url = await get_card_image_by_id(pokemon_id, set_name)
                
                if image_url:
                    try:
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                card_img = Image.open(io.BytesIO(img_data))
                                # Обрезаем и вписываем в слот
                                card_img = card_img.resize((CARD_WIDTH - 4, CARD_HEIGHT - 4))
                                background.paste(card_img, (x + 2, y + 2))
                    except Exception as e:
                        print(f"Ошибка загрузки карты {pokemon_id}: {e}")
                
                # Добавляем название карты
                name = card.get('name', '')[:25]
                draw.text((x + 5, y + CARD_HEIGHT - 25), name, fill=(255, 255, 255), font=font)
            
            else:
                # Пустой слот — рисуем силуэт вопроса
                draw.rectangle(
                    [x + 2, y + 2, x + CARD_WIDTH - 2, y + CARD_HEIGHT - 2],
                    fill=(40, 40, 50)
                )
                draw.text(
                    (x + CARD_WIDTH // 2 - 15, y + CARD_HEIGHT // 2 - 15),
                    "?",
                    fill=(100, 100, 120),
                    font=font
                )
    
    # Добавляем номер страницы
    draw.text((ALBUM_WIDTH - 80, ALBUM_HEIGHT - 30), f"Стр. {page_number}", fill=(200, 200, 200), font=font)
    
    # Сохраняем в BytesIO
    img_buffer = io.BytesIO()
    background.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    return img_buffer