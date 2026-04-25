ALBUM_WIDTH = 1024
ALBUM_HEIGHT = 1024

# Размеры карт
CARD_WIDTH = 280
CARD_HEIGHT = 380

# Отступы
MARGIN_X = 30      # между картами по горизонтали
MARGIN_Y = 30      # между рядами
OFFSET_X = 50      # отступ слева
OFFSET_Y = 80      # отступ сверху

# Количество карт на странице
CARDS_PER_PAGE = 6  # 3 колонки × 2 ряда

# Генерация слотов для одной страницы
def get_slots_for_page(page_number: int, start_id: int = 1):
    """
    Возвращает словарь слотов для указанной страницы
    page_number: номер страницы (1, 2, 3...)
    start_id: с какого ID карты начинается страница
    """
    slots = {}
    slot_index = 0
    
    for row in range(2):      # 2 ряда
        for col in range(3):  # 3 колонки
            x = OFFSET_X + col * (CARD_WIDTH + MARGIN_X)
            y = OFFSET_Y + row * (CARD_HEIGHT + MARGIN_Y)
            pokemon_id = start_id + slot_index
            slots[pokemon_id] = {
                "x": x, "y": y,
                "width": CARD_WIDTH, "height": CARD_HEIGHT,
                "slot_index": slot_index + 1
            }
            slot_index += 1
    
    return slots

# Путь к фону
ALBUM_BACKGROUND = "data/album_background.png"