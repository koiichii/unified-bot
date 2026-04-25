import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
import asyncio
from utils.weights import (
    POKEMON_DB_151, 
    POKEMON_DB_PRISMA, 
    NORMAL_WEIGHTS_151, 
    NORMAL_WEIGHTS_PRISMA,
    open_pack,
    open_pack_151
)
from utils.database import db
import sys
from utils.album_renderer import create_album_page

sys.path.append('C:/Users/bilya/unified_bot')


# ==================== AUTOCOMPLETE ФУНКЦИИ ====================

async def pack_autocomplete(interaction: discord.Interaction, current: str):
    packs = [
        ("151 Booster - 10 баксов", "151"),
        ("Prismatic Evolution Booster - 20 баксов", "prismatic")
    ]
    return [
        app_commands.Choice(name=name, value=value)
        for name, value in packs if current.lower() in name.lower()
    ][:25]

async def sell_autocomplete(interaction: discord.Interaction, current: str):
    collection = await db.get_user_collection(interaction.user.id)
    
    if not collection["pokemons"]:
        return []
    
    # Получаем дубликаты для подсчёта количества
    all_duplicates = await db.get_user_duplicates(interaction.user.id)
    duplicate_counts = {}
    for dup in all_duplicates:
        duplicate_counts[dup['pokemon_id']] = duplicate_counts.get(dup['pokemon_id'], 0) + 1
    
    suggestions = []
    for p in collection["pokemons"]:
        pokemon = next((card for card in POKEMON_DB_151 + POKEMON_DB_PRISMA 
                    if card["id"] == p["pokemon_id"]), None)
        if pokemon:
            name = pokemon['name']
            price = pokemon['price']
            count = duplicate_counts.get(p["pokemon_id"], 0) + 1
            display_name = f"{name} — ${price} (x{count})"
            
            if current.lower() in name.lower():
                suggestions.append(app_commands.Choice(name=display_name[:100], value=name))
    
    return suggestions[:25]


# ==================== КНОПКИ ДЛЯ ПАКА ====================

class PackActions(discord.ui.View):
    def __init__(self, pack_cards, pack_info, owner_id, guild_id):
        super().__init__(timeout=120)
        self.pack_cards = pack_cards
        self.pack_info = pack_info  # (cost, source, pack_name)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.image_messages = []  
        self.text_message = None 
    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Эти кнопки только для того, кто открыл пак!", ephemeral=True)
            return False
        return True
    async def delete_messages(self):
        for msg in self.image_messages:
            try:
                await msg.delete()
            except:
                pass
        if self.text_message:
            try:
                await self.text_message.delete()
            except:
                pass
    @discord.ui.button(label="💰 Продать дубликаты", style=discord.ButtonStyle.danger)
    async def sell_duplicates(self, interaction, button):
        await interaction.response.defer()
        await self.delete_messages()
        collection = await db.get_user_collection(self.owner_id)
        
        sold_count = 0
        sold_total = 0
        
        for pokemon in self.pack_cards:
            existing = next((p for p in collection["pokemons"] if p["pokemon_id"] == pokemon["id"]), None)
            if existing is not None:
                sold_count += 1
                sold_total += pokemon['price']
        
        await db.update_user_money(self.owner_id, self.guild_id, round(sold_total, 2))
        balance = await db.get_user_money(self.owner_id, self.guild_id)
        
        await interaction.followup.send(
            f"💰 Продано {sold_count} дубликатов на сумму ${round(sold_total, 2)}!\n"
            f"💵 Баланс: ${round(balance, 2)}",
            ephemeral=True
        )
    @discord.ui.button(label="📦 Принять все", style=discord.ButtonStyle.success)
    async def accept_all(self, interaction, button):
        await interaction.response.defer()  # ← СНАЧАЛА defer
        await self.delete_messages()       # ← ПОТОМ удаление
        await interaction.followup.send(
            f"✅ Все {len(self.pack_cards)} карт уже в коллекции!",
            ephemeral=True
        )

    @discord.ui.button(label="🔄 Открыть еще", style=discord.ButtonStyle.primary)
    async def open_another(self, interaction, button):
        print("DEBUG: open_another вызвана")
        try:
            await interaction.response.defer()
            print("DEBUG: Defer выполнен")

            await self.delete_messages()
            print("DEBUG: Сообщения удалены")

            cost, source, pack_name = self.pack_info
            print(f"DEBUG: cost={cost}, source={source}, pack_name={pack_name}")

            if pack_name == "151":
                pokemon_db = POKEMON_DB_151
                normal_weights = NORMAL_WEIGHTS_151
            else:
                pokemon_db = POKEMON_DB_PRISMA
                normal_weights = NORMAL_WEIGHTS_PRISMA

            user_balance = await db.get_user_money(self.owner_id, self.guild_id)
            print(f"DEBUG: user_balance={user_balance}, cost={cost}")

            if user_balance < cost:
                await interaction.followup.send(f"❌ Нужно {cost} монет!", ephemeral=True)
                return

            print("DEBUG: Открываем новый пак")
            if pack_name == "151":
                new_pack = open_pack_151(pokemon_db, normal_weights)
            else:
                new_pack = open_pack(pokemon_db, normal_weights)
            print(f"DEBUG: Новый пак открыт, {len(new_pack)} карт")

            for card in new_pack:
                await db.add_pokemon_to_collection(self.owner_id, card["id"], source, card['name'])

            await db.update_user_money(self.owner_id, self.guild_id, round(-cost, 2))

            new_view = PackActions(new_pack, (cost, source, pack_name), self.owner_id, self.guild_id)

            for idx, card in enumerate(new_pack):
                try:
                    print(f"DEBUG: Отправка изображения {idx+1} для {card['name']}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(card['image']) as resp:
                            if resp.status == 200:
                                image_data = await resp.read()
                                msg = await interaction.followup.send(
                                    file=discord.File(fp=io.BytesIO(image_data), filename=f"SPOILER_{card['name']}.png")
                                )
                                new_view.image_messages.append(msg)
                                print(f"DEBUG: Изображение {card['name']} отправлено")
                            else:
                                print(f"DEBUG: Ошибка загрузки {card['name']}: статус {resp.status}")
                except Exception as e:
                    print(f"Ошибка: {e}")

            result_text = f"🎴 **{interaction.user.mention}** открыл пак {pack_name} за ${cost}!\n\n"
            for i, card in enumerate(new_pack, 1):
                result_text += f"||{i}. **{card['name']}** — ${card['price']}||\n"

            msg = await interaction.followup.send(result_text, view=new_view)
            new_view.text_message = msg
            print("DEBUG: open_another завершена")

        except Exception as e:
            print(f"ERROR в open_another: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
# ==================== ОСНОВНОЙ КОГ ====================

class PokemonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== GACHA ====================
    
    @app_commands.command(name='gacha', description='Открыть пак с покемонами')
    @app_commands.autocomplete(pack=pack_autocomplete)
    async def gacha(self, interaction: discord.Interaction, pack: str):
        """Открыть пак с покемонами"""
        await interaction.response.defer()
        
        if pack == "151":
            cost, source, pack_name = 10, "151", "151"
        else:
            cost, source, pack_name = 20, "Prismatic Evolution", "Prismatic Evolution"
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_balance = await db.get_user_money(interaction.user.id, guild_id)
        
        if user_balance < cost:
            await interaction.followup.send(f"❌ Недостаточно денег! Нужно {cost} монет. А у тебя {user_balance}")
            return
        
        # Открытие пака
        if pack_name == "151":
            pokemon_db = POKEMON_DB_151
            normal_weights = NORMAL_WEIGHTS_151
            pack_cards = open_pack_151(pokemon_db, normal_weights)
        else:
            pokemon_db = POKEMON_DB_PRISMA
            normal_weights = NORMAL_WEIGHTS_PRISMA
            pack_cards = open_pack(pokemon_db, normal_weights)
        
        # Сохранение карт
        for card in pack_cards:
            await db.add_pokemon_to_collection(interaction.user.id, card["id"], source, card['name'])
        
        # Списание монет
        await db.update_user_money(interaction.user.id, guild_id, round(-cost))

        view = PackActions(pack_cards, (cost, source, pack_name), interaction.user.id, guild_id)

# Отправка изображений (теперь view существует)
        for card in pack_cards:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(card['image']) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            msg = await interaction.followup.send(
                                file=discord.File(
                                    fp=io.BytesIO(image_data),
                                    filename=f"SPOILER_{card['name']}.png"
                                )
                            )
                            view.image_messages.append(msg)
            except Exception as e:
                print(f"Ошибка загрузки {card['name']}: {e}")

# Текстовый результат
        result_text = f"🎴 **{interaction.user.mention}** открыл пак {pack_name} за ${cost}!\n\n"
        for i, card in enumerate(pack_cards, 1):
            result_text += f"||{i}. **{card['name']}** — ${card['price']}||\n"

        msg = await interaction.followup.send(result_text, view=view)
        view.text_message = msg



    # ==================== TEST_CHANCE ====================
    
    @app_commands.command(name='test_chance', description='Тест вероятностей выпадения карт')
    async def test_chance(self, interaction: discord.Interaction, packs: int):
        """Тест вероятностей на N паках"""
        await interaction.response.defer()
        
        # Здесь можно добавить выбор сета, пока оба
        pokemon_db = POKEMON_DB_PRISMA
        normal_weights = NORMAL_WEIGHTS_PRISMA
        cost = 20
        
        count_price = 0
        count_sir = 0
        count_ir = 0
        count_ur = 0
        count_hr = 0
        count_rr = 0
        count_r = 0
        count_u = 0
        count_c = 0
        count_1000 = 0
        count_750 = 0
        count_500 = 0
        count_250 = 0
        count_100 = 0
        count_50 = 0
        
        slot_rare_counts = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        
        for _ in range(packs):
            pack = open_pack(pokemon_db, normal_weights)
            for slot_index, pokemon in enumerate(pack):
                count_price += pokemon["price"]
                
                if pokemon['rarity'] == "Special_illustration_rare":
                    count_sir += 1
                elif pokemon['rarity'] == "Illustration_rare":
                    count_ir += 1
                elif pokemon['rarity'] == "Ultra_rare":
                    count_ur += 1 
                elif pokemon['rarity'] == "Hyper_rare":
                    count_hr += 1 
                elif pokemon['rarity'] == "Double_rare":
                    count_rr += 1
                elif pokemon['rarity'] == "Rare":
                    count_r += 1
                elif pokemon['rarity'] == "Uncommon":
                    count_u += 1 
                else:  
                    count_c += 1
                
                if pokemon['price'] > 1000:
                    count_1000 += 1 
                elif 750 <= pokemon['price'] <= 1000:
                    count_750 += 1
                elif 500 <= pokemon['price'] < 750:
                    count_500 += 1
                elif 250 <= pokemon['price'] < 500:
                    count_250 += 1
                elif 100 <= pokemon['price'] < 250:
                    count_100 += 1
                elif 50 <= pokemon['price'] < 100:
                    count_50 += 1
                
                is_rare_plus = pokemon['rarity'] in ["Rare", "Double_rare", "Ultra_rare", 
                                                      "Illustration_rare", "Special_illustration_rare", 
                                                      "Hyper_rare"]
                if is_rare_plus:
                    slot_rare_counts[slot_index] += 1
        
        total_cost = cost * packs
        lose = total_cost - count_price
        around_pack = count_price / packs if packs > 0 else 0
        
        slot_stats = []
        for i, count in enumerate(slot_rare_counts, 1):
            slot_stats.append(f"Слот {i}: {count} ({round(count / packs * 100, 2)}%)")
        slot_stats_text = "\n".join(slot_stats)
        
        await interaction.followup.send(
            f'📊 **Тест Prismatic Evolution**\n'
            f'Открыто: **{packs}** паков\n'
            f'Сумма выигрыша: **${round(count_price, 1)}**\n'
            f'SIR: **{count_sir}** | IR: **{count_ir}** | UR: **{count_ur}**\n'
            f'HR: **{count_hr}** | RR: **{count_rr}** | R: **{count_r}**\n'
            f'U: **{count_u}** | C: **{count_c}**\n\n'
            f'💰 Потрачено: **${total_cost}**\n'
            f'📉 Игрок **{"потерял" if lose > 0 else "выиграл"} ${abs(round(lose, 1))}**\n'
            f'📊 Средняя стоимость пака: **${round(around_pack, 1)}**\n\n'
            f'💎 >$1000: **{count_1000}** | $750-1000: **{count_750}**\n'
            f'💎 $500-750: **{count_500}** | $250-500: **{count_250}**\n'
            f'💎 $100-250: **{count_100}** | $50-100: **{count_50}**\n\n'
            f'📊 **Статистика выпадения Rare+ по слотам:**\n{slot_stats_text}'
        )


    # ==================== SELLDUBL ====================
    
    @app_commands.command(name='selldubl', description='Продать все дубликаты из коллекции')
    async def selldubl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        guild_id = interaction.guild.id if interaction.guild else 0
        collection = await db.get_user_collection(interaction.user.id)
        
        if not collection["duplicates"]:
            await interaction.followup.send("❌ У вас нет дубликатов для продажи!", ephemeral=True)
            return
        
        sold_total = await db.sell_all_duplicates(interaction.user.id)
        await db.update_user_money(interaction.user.id, guild_id, round(sold_total, 2))
        balance = await db.get_user_money(interaction.user.id, guild_id)
        
        await interaction.followup.send(
            f"💰 Продано {len(collection['duplicates'])} дубликатов на сумму ${round(sold_total, 2)}!\n"
            f"💵 Ваш баланс: ${round(balance, 2)}"
        )


    # ==================== ADD_MONEY ====================
    
    @app_commands.command(name='add_money', description='Добавить монеты пользователю (только для админов)')
    @app_commands.default_permissions(administrator=True)
    async def add_money(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await interaction.response.defer()
        guild_id = interaction.guild.id if interaction.guild else 0
        await db.update_user_money(member.id, guild_id, amount)
        await interaction.followup.send(f"✅ Пользователю {member.mention} добавлено {amount} баксов!")


    # ==================== COLLECTION ====================
    
    @commands.guild_only()
    @app_commands.command(name='collection', description='Показать коллекцию покемонов игрока (альбом)')
    async def collection(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
    
        member = interaction.user
    
        # Получаем коллекцию пользователя
        collection = await db.get_user_collection(member.id)
    
        if not collection["pokemons"]:
            await interaction.followup.send(f"📭 У игрока {member.mention} пока нет ни одного покемона в коллекции!")
            return
    
        # Получаем карты пользователя в формате {pokemon_id: card_data}
        user_cards = {p['pokemon_id']: p for p in collection["pokemons"]}
    
        # Для Prismatic Evolution карты имеют ID от 188 до 310
        # Определяем максимальный ID для сета (нужно подобрать под твои данные)
        # Если карты из 151 сета — ID до 187, если Prismatic — с 188
        # Пока сделаем для Prismatic (можно добавить выбор сета позже)
        max_card_id = 310  # максимальный ID карты в твоей БД
    
        total_pages = (max_card_id + 5) // 6  # 6 карт на страницу
    
        class AlbumView(discord.ui.View):
            def __init__(self, user_id, user_cards, current_page=1):
                super().__init__(timeout=120)
                self.user_id = user_id
                self.user_cards = user_cards
                self.current_page = current_page
                self.total_pages = total_pages
                self.message = None  # ← сохраняем сообщение

            async def update_page(self, interaction, page):
                img = await create_album_page(self.user_id, "prismatic", page, self.user_cards)
                # Обновляем существующее сообщение, а не отправляем новое
                await interaction.response.edit_message(
                    file=discord.File(img, filename=f"album_page_{page}.png"),
                    view=self
                )

            @discord.ui.button(label="◀ Назад", style=discord.ButtonStyle.primary)
            async def prev_page(self, interaction, button):
                if self.current_page > 1:
                    self.current_page -= 1
                    await self.update_page(interaction, self.current_page)

            @discord.ui.button(label="Вперед ▶", style=discord.ButtonStyle.primary)
            async def next_page(self, interaction, button):
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    await self.update_page(interaction, self.current_page)

            @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.secondary)
            async def close(self, interaction, button):
                await interaction.response.delete_message()
    
        # Создаём первую страницу
        img = await create_album_page(member.id, "prismatic", 1, user_cards)
        view = AlbumView(member.id, user_cards)
        await interaction.followup.send(file=discord.File(img, filename="album_page_1.png"), view=view)


    # ==================== SELL ====================
    
    @app_commands.command(name='sell', description='Продать конкретную карту из коллекции')
    @app_commands.autocomplete(card_name=sell_autocomplete)
    async def sell(self, interaction: discord.Interaction, card_name: str):
        await interaction.response.defer()
        
        # Очищаем название от цены и количества
        clean_name = card_name.split(' — $')[0] if ' — $' in card_name else card_name
        
        guild_id = interaction.guild.id if interaction.guild else 0
        collection = await db.get_user_collection(interaction.user.id)
        
        if not collection["pokemons"]:
            await interaction.followup.send("❌ У вас нет карт для продажи!", ephemeral=True)
            return
        
        found_card = None
        found_pokemon = None
        
        for p in collection["pokemons"]:
            pokemon = next((card for card in POKEMON_DB_151 + POKEMON_DB_PRISMA if card["id"] == p["pokemon_id"]), None)
            if pokemon and pokemon['name'].lower() == clean_name.lower():
                found_card = p
                found_pokemon = pokemon
                break
        
        if found_card is None:
            await interaction.followup.send(f"❌ Карта `{clean_name}` не найдена в вашей коллекции!", ephemeral=True)
            return
        
        # Создаём кнопки для подтверждения
        class ConfirmView(discord.ui.View):
            def __init__(self, user_id, card_data, pokemon_data, guild_id):
                super().__init__(timeout=60)
                self.user_id = user_id
                self.card_data = card_data
                self.pokemon_data = pokemon_data
                self.guild_id = guild_id
                self.confirmed = False
            
            @discord.ui.button(label="✅ Да, продать", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction, button):
                if button_interaction.user.id != self.user_id:
                    await button_interaction.response.send_message("❌ Это не ваша команда!", ephemeral=True)
                    return
                
                await button_interaction.response.defer()
                self.confirmed = True
                await db.remove_pokemon_from_collection(self.user_id, self.card_data["pokemon_id"])
                price = self.pokemon_data["price"]
                await db.update_user_money(self.user_id, self.guild_id, round(price, 2))
                balance = await db.get_user_money(self.user_id, self.guild_id)
                
                await button_interaction.followup.send(
                    f"💰 Продана карта **{self.pokemon_data['name']}** за **${price}**!\n"
                    f"💵 Ваш баланс: **${round(balance, 2)}**",
                    ephemeral=True
                )
                self.stop()
            
            @discord.ui.button(label="❌ Нет, отмена", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction, button):
                if button_interaction.user.id != self.user_id:
                    await button_interaction.response.send_message("❌ Это не ваша команда!", ephemeral=True)
                    return
                
                await button_interaction.response.send_message("❌ Продажа отменена.", ephemeral=True)
                self.stop()
            
            async def on_timeout(self):
                if not self.confirmed:
                    await interaction.followup.send("⏰ Время вышло. Продажа отменена.", ephemeral=True)
        
        embed = discord.Embed(
            title="💸 Подтверждение продажи",
            description=f"Вы уверены, что хотите продать эту карту?",
            color=discord.Color.red()
        )
        embed.add_field(name="Карта", value=f"**{found_pokemon['name']}**", inline=False)
        embed.add_field(name="Редкость", value=found_pokemon['rarity'], inline=True)
        embed.add_field(name="Цена", value=f"**${found_pokemon['price']}**", inline=True)
        embed.set_footer(text="Это действие нельзя отменить!")
        
        view = ConfirmView(interaction.user.id, found_card, found_pokemon, guild_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=False)


async def setup(bot):
    await bot.add_cog(PokemonCog(bot))