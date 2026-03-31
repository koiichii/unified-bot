from utils.database import db

def check_and_add_coins(amount: int = 100):
    """Декоратор для начисления монет при вызове команды"""
    def decorator(func):
        async def wrapper(self, ctx, *args, **kwargs):
            guild_id = ctx.guild.id if ctx.guild else 0
            user_data = await db.get_user(ctx.author.id, guild_id)
            
            # Добавляем монеты
            await db.update_user_money(ctx.author.id, guild_id, amount)
            
            # Выполняем основную команду
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator