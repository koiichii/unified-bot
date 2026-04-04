# cogs/pokemon.py
import discord
from discord.ext import commands
import os
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
from utils.prices import get_pokemon_price_by_id
import sys
from utils.decorators import check_and_add_coins

sys.path.append('C:/Users/bilya/unified_bot')


class PokemonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================== КОМАНДА GACHA ====================
    
    @commands.command(name='gacha')
    async def gacha(self, ctx):
        class BoxSelector(discord.ui.View):
            def __init__(self, original_message):
                super().__init__(timeout=60)
                self.original_message = original_message

            @discord.ui.button(label="151 Booster - 10 баксов", style=discord.ButtonStyle.primary)
            async def booster_151(self, interaction, button):
                print("DEBUG: Нажата кнопка 151 Booster")
                await interaction.response.defer()
                await self.process_gacha(interaction, cost=10, source="151", pack_name="151")

            @discord.ui.button(label="Prismatic Evolution Booster - 20 баксов", style=discord.ButtonStyle.success)
            async def booster_prisma(self, interaction, button):
                print("DEBUG: Нажата кнопка Prismatic Booster")
                await interaction.response.defer()
                await self.process_gacha(interaction, cost=20, source="Prismatic Evolution", pack_name="Prismatic Evolution")

            async def process_gacha(self, interaction, cost, source, pack_name):
                try:
                    print(f"DEBUG: Начало process_gacha | cost={cost}, source={source}, pack_name={pack_name}")
                    grade = 0

                    # Удаляем исходное сообщение
                    try:
                        await self.original_message.delete()
                        print("DEBUG: Исходное сообщение удалено")
                    except Exception as e:
                        print(f"DEBUG: Ошибка удаления исходного сообщения: {e}")

                    # Выбор базы данных
                    print(f"DEBUG: Выбор базы данных для {pack_name}")
                    if pack_name == "151":
                        pokemon_db = POKEMON_DB_151
                        normal_weights = NORMAL_WEIGHTS_151
                        print(f"DEBUG: Загружено {len(pokemon_db)} карт из 151 сета")
                    else:
                        pokemon_db = POKEMON_DB_PRISMA
                        normal_weights = NORMAL_WEIGHTS_PRISMA
                        print(f"DEBUG: Загружено {len(pokemon_db)} карт из Prismatic сета")

                    # Получение данных пользователя
                    guild_id = interaction.guild.id if interaction.guild else 0
                    user_balance = await db.get_user_money(interaction.user.id, guild_id)

                    if user_balance < cost:
                        await interaction.followup.send(f"❌ Недостаточно денег! Нужно {cost} монет. А у тебя {user_balance}", ephemeral=True)
                        return

                    # Открытие пака
                    print("DEBUG: Открытие пака...")
                    if pack_name == "151":
                        pack = open_pack_151(pokemon_db, normal_weights)
                    else:
                        pack = open_pack(pokemon_db, normal_weights)
                    print(f"DEBUG: Открыто {len(pack)} карт")

                    # Списание монет
                    print(f"DEBUG: Списание {cost} монет")
                    await db.update_user_money(interaction.user.id, guild_id, -cost)

                    # Отправка изображений
                    print("DEBUG: Отправка изображений...")
                    image_messages = []
                    for idx, card in enumerate(pack):
                        try:
                            if 'image' not in card or not card['image']:
                                print(f"DEBUG: Карта {idx+1} - нет изображения")
                                continue
                            print(f"DEBUG: Загрузка изображения для {card['name']}")
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
                                        image_messages.append(msg)
                                        print(f"DEBUG: Изображение {card['name']} отправлено")
                                    else:
                                        print(f"DEBUG: Ошибка загрузки {card['name']}: статус {resp.status}")
                        except Exception as e:
                            print(f"DEBUG: Ошибка при загрузке {card['name']}: {e}")

                    # Текстовый результат
                    print("DEBUG: Формирование текстового результата")
                    result_text = f"🎴 **{interaction.user.mention}** открыл пак {pack_name} за ${cost}!\n\n"
                    for i, card in enumerate(pack, 1):
                        result_text += f"||{i}. **{card['name']}** ({card['rarity']}) — ${card['price']}||\n"

                    # Класс с кнопками действий
                    class PackActions(discord.ui.View):
                        def __init__(self, pack_cards, image_msgs, pack_info, owner_id, guild_id, auto_save=True):
                            super().__init__(timeout=120)
                            self.pack_cards = pack_cards
                            self.image_messages = image_msgs
                            self.pack_info = pack_info
                            self.owner_id = owner_id
                            self.guild_id = guild_id
                            self.text_message = None
                            self.auto_saved = False
                            if auto_save:
                                self.auto_save_task = asyncio.create_task(self.auto_save())

                        async def auto_save(self):
                            await asyncio.sleep(120)
                            if not self.auto_saved:
                                await self.save_all_cards()
                                await self.delete_messages()

                        async def save_all_cards(self):
                            if self.auto_saved:
                                return
                            self.auto_saved = True
                            # Сохраняем все карты в БД
                            for pokemon in self.pack_cards:
                                await db.add_pokemon_to_collection(self.owner_id, pokemon["id"], self.pack_info[1])

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
                        async def sell_duplicates(self, interaction_button, button):
                            print("DEBUG: Кнопка sell_duplicates нажата")
                            await interaction_button.response.defer()
                            print("DEBUG: Defer выполнен")

                            self.auto_saved = True
                            if hasattr(self, 'auto_save_task'):
                                self.auto_save_task.cancel()
                                print("DEBUG: Auto-save отменён")

                            print(f"DEBUG: owner_id = {self.owner_id}")
                            print(f"DEBUG: guild_id = {self.guild_id}")

                            try:
                                # Получаем коллекцию из БД
                                collection = await db.get_user_collection(self.owner_id)
                                print(f"DEBUG: Коллекция получена, дубликатов: {len(collection['duplicates'])}")

                                sold_count = 0
                                sold_total = 0
                                new_cards = []

                                for pokemon in self.pack_cards:
                                    # Проверяем, есть ли карта в уникальных
                                    existing = next((p for p in collection["pokemons"] if p["pokemon_id"] == pokemon["id"]), None)
                                    if existing is not None:
                                        sold_count += 1
                                        sold_total += pokemon['price']
                                        print(f"DEBUG: Дубликат {pokemon['name']} продан за ${pokemon['price']}")
                                    else:
                                        new_cards.append(pokemon)
                                        print(f"DEBUG: Новая карта {pokemon['name']} добавлена в коллекцию")
                                        await db.add_pokemon_to_collection(self.owner_id, pokemon["id"], self.pack_info[1])

                                print(f"DEBUG: Продано {sold_count} дубликатов на сумму ${sold_total}")

                                # Обновляем баланс в базе данных
                                print(f"DEBUG: Обновление баланса пользователя {self.owner_id} на +{sold_total}")
                                await db.update_user_money(self.owner_id, self.guild_id, sold_total)
                                print("DEBUG: Баланс обновлён")

                                await self.delete_messages()
                                print("DEBUG: Сообщения удалены")

                                # Получаем актуальный баланс
                                balance = await db.get_user_money(self.owner_id, self.guild_id)
                                print(f"DEBUG: Новый баланс: ${balance}")

                                await interaction_button.followup.send(
                                    f"💰 Продано {sold_count} дубликатов на сумму ${round(sold_total, 2)}!\n"
                                    f"✨ Добавлено {len(new_cards)} новых карт.\n"
                                    f"💵 Баланс: ${round(balance, 2)}",
                                    ephemeral=True
                                )
                                print("DEBUG: Ответ отправлен")

                            except Exception as e:
                                print(f"ERROR в sell_duplicates: {e}")
                                import traceback
                                traceback.print_exc()
                                await interaction_button.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

                        @discord.ui.button(label="📦 Принять все", style=discord.ButtonStyle.success)
                        async def accept_all(self, interaction_button, button):
                            await interaction_button.response.defer()
                            self.auto_saved = True
                            if hasattr(self, 'auto_save_task'):
                                self.auto_save_task.cancel()
                            
                            # Сохраняем все карты в БД
                            for pokemon in self.pack_cards:
                                await db.add_pokemon_to_collection(self.owner_id, pokemon["id"], self.pack_info[1])
                            
                            await self.delete_messages()
                            
                            await interaction_button.followup.send(
                                f"✅ Все {len(self.pack_cards)} карт добавлены в коллекцию!",
                                ephemeral=True
                            )

                        @discord.ui.button(label="🔄 Открыть еще", style=discord.ButtonStyle.primary)
                        async def open_another(self, interaction_button, button):
                            await interaction_button.response.defer()
                            self.auto_saved = True
                            if hasattr(self, 'auto_save_task'):
                                self.auto_save_task.cancel()
                            await self.delete_messages()
                            
                            cost, source, pack_name = self.pack_info
                            
                            if pack_name == "151":
                                pokemon_db = POKEMON_DB_151
                                normal_weights = NORMAL_WEIGHTS_151
                            else:
                                pokemon_db = POKEMON_DB_PRISMA
                                normal_weights = NORMAL_WEIGHTS_PRISMA
                            
                            # Проверяем баланс
                            user_balance = await db.get_user_money(self.owner_id, self.guild_id)
                            if user_balance is None or user_balance < cost:
                                await interaction_button.followup.send(f"❌ Нужно {cost} монет!", ephemeral=True)
                                return
                            
                            if pack_name == "151":
                                new_pack = open_pack_151(pokemon_db, normal_weights)
                            else:
                                new_pack = open_pack(pokemon_db, normal_weights)
                            
                            # Списываем монеты
                            await db.update_user_money(self.owner_id, self.guild_id, -cost)
                            
                            new_image_messages = []
                            for card in new_pack:
                                try:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(card['image']) as resp:
                                            if resp.status == 200:
                                                image_data = await resp.read()
                                                msg = await interaction_button.followup.send(
                                                    file=discord.File(fp=io.BytesIO(image_data), filename=f"SPOILER_{card['name']}.png")
                                                )
                                                new_image_messages.append(msg)
                                except Exception as e:
                                    print(f"Ошибка: {e}")
                            
                            result_text = f"🎴 **{interaction_button.user.mention}** открыл пак {pack_name} за ${cost}!\n\n"
                            for i, card in enumerate(new_pack, 1):
                                result_text += f"||{i}. **{card['name']}** ({card['rarity']}) — ${card['price']}||\n"
                            
                            new_view = PackActions(new_pack, new_image_messages, (cost, source, pack_name), self.owner_id, self.guild_id)
                            msg = await interaction_button.followup.send(result_text, view=new_view)
                            new_view.text_message = msg
                            
                            # Сохраняем карты нового пака в БД
                            for pokemon in new_pack:
                                await db.add_pokemon_to_collection(self.owner_id, pokemon["id"], source)

                    # Отправка сообщения с кнопками
                    print("DEBUG: Отправка сообщения с кнопками")
                    view = PackActions(pack, image_messages, (cost, source, pack_name), interaction.user.id, guild_id)
                    msg = await interaction.followup.send(result_text, view=view)
                    view.text_message = msg
                    print("DEBUG: process_gacha успешно завершен")

                except Exception as e:
                    print(f"ERROR в process_gacha: {e}")
                    import traceback
                    traceback.print_exc()
                    await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

        view = BoxSelector(ctx.message) 
        await ctx.send("**Выбери сундук:**", view=view)


    # ==================== КОМАНДА TEST_CHANCE ====================
    
    @commands.command(name='test_chance')
    async def test_chance(self, ctx, arg: int):
        class BoxSelector(discord.ui.View):
            def __init__(self, original_message):
                super().__init__(timeout=60)
                self.original_message = original_message

            @discord.ui.button(label="151 Booster - 10 баксов", style=discord.ButtonStyle.primary)
            async def booster_151(self, interaction, button):
                await interaction.response.defer()
                await self.process_gacha(interaction, arg=arg, pack_name="151")

            @discord.ui.button(label="Prismatic Evolution Booster - 20 баксов", style=discord.ButtonStyle.success)
            async def booster_prisma(self, interaction, button):
                await interaction.response.defer()
                await self.process_gacha(interaction, arg=arg, pack_name="Prismatic Evolution")

            async def process_gacha(self, interaction, arg, pack_name):
                try:
                    await self.original_message.delete()
                except:
                    pass

                if pack_name == "151":
                    pokemon_db = POKEMON_DB_151
                    normal_weights = NORMAL_WEIGHTS_151
                    cost = 10
                else:
                    pokemon_db = POKEMON_DB_PRISMA
                    normal_weights = NORMAL_WEIGHTS_PRISMA
                    cost = 20

                # Отладка в консоль
                print(f"\n=== ТЕСТ: {pack_name} | {arg} паков ===")
                print(f"Всего карт в базе: {len(pokemon_db)}")
                
                for p in pokemon_db:
                    if "Umbreon" in p['name'] and "SIR" in p['name']:
                        idx = pokemon_db.index(p)
                        print(f"Umbreon ex SIR цена: ${p['price']}")
                        print(f"Вес Umbreon: {normal_weights[idx]:.8f}")
                        break
                
                for p in pokemon_db:
                    if p['rarity'] == "Common" and p['price'] < 1:
                        idx = pokemon_db.index(p)
                        print(f"Обычная карта: {p['name'][:30]} цена: ${p['price']}")
                        print(f"Вес обычной карты: {normal_weights[idx]:.4f}")
                        break
                
                print(f"Сумма весов: {sum(normal_weights):.4f}")
                print("====================\n")

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

                for _ in range(arg):
                    if pack_name == "151":
                        pack = open_pack_151(pokemon_db, normal_weights)
                    else:
                        pack = open_pack(pokemon_db, normal_weights)
                        
                    for pokemon in pack:
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
                
                total_cost = cost * arg
                lose = total_cost - count_price
                around_pack = count_price / arg if arg > 0 else 0

                await interaction.followup.send(f'📊 **Тест {pack_name}**\n'
                               f'Открыто: **{arg}** паков\n'
                               f'Сумма выигрыша: **${round(count_price, 1)}**\n'
                               f'SIR: **{count_sir}** | IR: **{count_ir}** | UR: **{count_ur}**\n'
                               f'HR: **{count_hr}** | RR: **{count_rr}** | R: **{count_r}**\n'
                               f'U: **{count_u}** | C: **{count_c}**\n\n'
                               f'💰 Потрачено: **${total_cost}**\n'
                               f'📉 Игрок **{"потерял" if lose > 0 else "выиграл"} ${abs(round(lose, 1))}**\n'
                               f'📊 Средняя стоимость пака: **${round(around_pack, 1)}**\n\n'
                               f'💎 >$1000: **{count_1000}** | $750-1000: **{count_750}**\n'
                               f'💎 $500-750: **{count_500}** | $250-500: **{count_250}**\n'
                               f'💎 $100-250: **{count_100}** | $50-100: **{count_50}**')

        view = BoxSelector(ctx.message) 
        await ctx.send("**Выбери сундук для теста:**", view=view)


    # ==================== КОМАНДА CELL (продажа всех дубликатов) ====================
    
    @commands.command(name='cell')
    async def сell(self, ctx):
        guild_id = ctx.guild.id if ctx.guild else 0
    
    # Получаем коллекцию из базы данных
        collection = await db.get_user_collection(ctx.author.id)
    
        if not collection["duplicates"]:
            await ctx.send("❌ У вас нет дубликатов для продажи!")
            return
    
    # Продаём все дубликаты
        sold_total = await db.sell_all_duplicates(ctx.author.id)
    
    # Обновляем баланс
        await db.update_user_money(ctx.author.id, guild_id, sold_total)
    
    # Получаем актуальный баланс
        balance = await db.get_user_money(ctx.author.id, guild_id)
    
        await ctx.send(
            f"💰 Продано {len(collection['duplicates'])} дубликатов на сумму ${round(sold_total, 2)}!\n"
            f"💵 Ваш баланс: ${round(balance, 2)}"
        )


    # ==================== КОМАНДА ADD_MONEY (для админов) ====================
    
    @commands.command(name='add_money')
    @commands.has_permissions(administrator=True)
    async def add_money(self, ctx, amount: int, member: discord.Member = None):
        """Добавить монеты пользователю (только для админов)"""
        if member is None:
            member = ctx.author
    
        guild_id = ctx.guild.id if ctx.guild else 0
        await db.update_user_money(member.id, guild_id, amount)
    
        await ctx.send(f"✅ Пользователю {member.mention} добавлено {amount} баксов!")

# ==================== КОМАНДА COLLECTION (показать коллекцию) ====================

    @commands.command(name='collection')
    async def collection(self, ctx, member: discord.Member = None):
        """Показать коллекцию покемонов игрока"""
        if member is None:
            member = ctx.author
        
        # Получаем коллекцию из БД
        collection = await db.get_user_collection(member.id)
        
        if not collection["pokemons"]:
            await ctx.send(f"📭 У игрока {member.mention} пока нет ни одного покемона в коллекции!")
            return
        
        # Сортируем карты по ID (или можно по имени)
        sorted_pokemons = sorted(collection["pokemons"], key=lambda x: x['pokemon_id'])
        
        # Получаем информацию о каждой карте
        pokemon_list = []
        for p in sorted_pokemons:
            # Ищем карту в базах данных
            pokemon = next((card for card in POKEMON_DB_151 + POKEMON_DB_PRISMA if card["id"] == p["pokemon_id"]), None)
            if pokemon:
                pokemon_list.append({
                    "name": pokemon['name'],
                    "rarity": pokemon['rarity'],
                    "price": pokemon['price'],
                    "source": p['source']
                })
        
        # Создаём embed для красивого отображения
        embed = discord.Embed(
            title=f"📦 Коллекция {member.display_name}",
            description=f"Всего уникальных карт: **{len(pokemon_list)}**",
            color=discord.Color.gold()
        )
        
        # Группируем по редкости
        sir_list = []
        ir_list = []
        ur_list = []
        hr_list = []
        rr_list = []
        rare_list = []
        uncommon_list = []
        common_list = []
        
        for p in pokemon_list:
            if p['rarity'] == "Special_illustration_rare":
                sir_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Illustration_rare":
                ir_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Ultra_rare":
                ur_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Hyper_rare":
                hr_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Double_rare":
                rr_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Rare":
                rare_list.append(f"• {p['name']} (${p['price']})")
            elif p['rarity'] == "Uncommon":
                uncommon_list.append(f"• {p['name']} (${p['price']})")
            else:
                common_list.append(f"• {p['name']} (${p['price']})")
        
        # Добавляем поля в embed (только непустые)
        if sir_list:
            embed.add_field(name=f"✨ Special Illustration Rare ({len(sir_list)})", 
                            value="\n".join(sir_list[:20]), inline=False)
            if len(sir_list) > 20:
                embed.add_field(name="", value=f"... и ещё {len(sir_list)-20} карт", inline=False)
        
        if ir_list:
            embed.add_field(name=f"🎨 Illustration Rare ({len(ir_list)})", 
                            value="\n".join(ir_list[:20]), inline=False)
            if len(ir_list) > 20:
                embed.add_field(name="", value=f"... и ещё {len(ir_list)-20} карт", inline=False)
        
        if ur_list:
            embed.add_field(name=f"⭐ Ultra Rare ({len(ur_list)})", 
                            value="\n".join(ur_list[:20]), inline=False)
        
        if hr_list:
            embed.add_field(name=f"🌟 Hyper Rare ({len(hr_list)})", 
                            value="\n".join(hr_list[:20]), inline=False)
        
        if rr_list:
            embed.add_field(name=f"💎 Double Rare ({len(rr_list)})", 
                            value="\n".join(rr_list[:15]), inline=False)
        
        if rare_list:
            embed.add_field(name=f"🔹 Rare ({len(rare_list)})", 
                            value="\n".join(rare_list[:15]), inline=False)
        
        if uncommon_list:
            embed.add_field(name=f"🟢 Uncommon ({len(uncommon_list)})", 
                            value="\n".join(uncommon_list[:10]), inline=False)
        
        if common_list:
            embed.add_field(name=f"⚪ Common ({len(common_list)})", 
                            value="\n".join(common_list[:10]), inline=False)
        
        embed.set_footer(text=f"Всего карт: {len(pokemon_list)} | Дубликатов: {len(collection['duplicates'])}")

        await member.send(embed=embed)

        if member != ctx.author:
            await ctx.send(f"📨 Коллекция игрока {member.mention} отправлена в личные сообщения!")


async def setup(bot):
    await bot.add_cog(PokemonCog(bot))