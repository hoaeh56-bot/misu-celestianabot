# relationship.py
import asyncpg
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging

router = Router()

# --- ЛОВИМ ЛЮБОЙ ТЕКСТ С "МОЙПОЛ" ИЛИ "МОЙ ПОЛ" ---
@router.message(F.text.lower().contains("мой"))
async def set_gender(message: Message, db: asyncpg.Pool):
    text = message.text.lower()
    
    # Проверяем, есть ли там "пол" и "м" или "ж"
    if "пол" not in text:
        return # Если это не про пол, пропускаем

    if text.endswith("м") or " м" in text:
        gender = "м"
    elif text.endswith("ж") or " ж" in text:
        gender = "ж"
    else:
        await message.reply("⚠️ Укажи пол: .мойпол м или .мойпол ж")
        return
    
    logging.info(f"Юзер {message.from_user.id} ставит пол {gender}")
    
    try:
        await db.execute(
            "INSERT INTO users (user_id, username, gender) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET gender = EXCLUDED.gender",
            message.from_user.id, message.from_user.username, gender
        )
        await message.reply(f"✅ Твой пол установлен: {'Мужской' if gender == 'м' else 'Женский'}.")
    except Exception as e:
        logging.error(f"Ошибка БД при смене пола: {e}")
        await message.reply("❌ Ошибка базы данных. Проверь логи на Render.")

# --- КОМАНДЫ .отн ---
@router.message(F.text.lower().startswith(".отн"))
async def relationship_handler(message: Message, db: asyncpg.Pool):
    text = message.text.lower()
    
    if "запрос" in text:
        if not message.reply_to_message:
            await message.reply("💔 Ответь на сообщение человека, с которым хочешь начать отношения.")
            return
        
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        initiator_id = message.from_user.id
        initiator_name = message.from_user.first_name
        
        if target_id == initiator_id:
            await message.reply("🤨 Нельзя вступить в отношения с самим собой.")
            return

        try:
            existing = await db.fetchrow(
                "SELECT * FROM couples WHERE chat_id = $1 AND status = 'ACTIVE' AND (user1_id = $2 OR user2_id = $2 OR user1_id = $3 OR user2_id = $3)",
                message.chat.id, initiator_id, target_id
            )
            
            if existing:
                await message.reply("❌ Один из вас уже состоит в отношениях в этом чате.")
                return

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data=f"accept_rel_{initiator_id}_{target_id}"),
                 InlineKeyboardButton(text="❌ Нет", callback_data="decline_rel")]
            ])
            
            await message.reply(
                f"💖 <b>{target_name}</b>, минутку внимания!\n"
                f"<b>{initiator_name}</b> предлагает тебе начать отношения.\n"
                f"У тебя есть 2 минуты, чтобы ответить.",
                reply_markup=kb
            )
        except Exception as e:
            logging.error(f"Ошибка БД при запросе: {e}")
            await message.reply("❌ Ошибка базы данных при создании запроса.")

    elif "я" in text:
        try:
            couple = await db.fetchrow(
                "SELECT * FROM couples WHERE chat_id = $1 AND status = 'ACTIVE' AND (user1_id = $2 OR user2_id = $2)",
                message.chat.id, message.from_user.id
            )
            
            if not couple:
                await message.reply("❌ У тебя пока нет пары в этом чате. Используй `.отн запрос`.")
                return

            partner_id = couple['user2_id'] if couple['user1_id'] == message.from_user.id else couple['user1_id']
            partner = await db.fetchrow("SELECT username FROM users WHERE user_id = $1", partner_id)
            partner_name = f"@{partner['username']}" if partner and partner['username'] else f"ID {partner_id}"

            profile_text = (
                f"❤️ <b>Твоя половинка:</b> {partner_name}\n"
                f"🆔 ID отношений: {couple['id']}\n"
                f"💎 <b>Искры:</b> {couple['sparks']}\n"
                f"📈 <b>Уровень:</b> {couple['level']}\n"
                f"🏠 <b>Дом:</b> Уютная квартира\n"
                f"👶 <b>Дети:</b> Нет\n"
                f"🐾 <b>Питомцы:</b> Нет\n"
                f"📊 <b>Действия:</b> 0 обычных / 0 премиум\n\n"
                f"<i>Искры тратятся на ежедневное содержание. Если упадут до 0 — отношения распадутся.</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Купить искры", callback_data="buy_sparks"),
                 InlineKeyboardButton(text="👑 Премиум", callback_data="buy_premium")],
                [InlineKeyboardButton(text="👶 Дети", callback_data="menu_children"),
                 InlineKeyboardButton(text="🤰 Беременность", callback_data="menu_pregnancy")],
                [InlineKeyboardButton(text="🏠 Дом", callback_data="menu_house"),
                 InlineKeyboardButton(text="🐾 Питомцы", callback_data="menu_pets")],
                [InlineKeyboardButton(text="🎁 Подарки", callback_data="menu_gifts"),
                 InlineKeyboardButton(text="📜 История", callback_data="menu_history")]
            ])
            
            await message.reply(profile_text, reply_markup=kb)
        except Exception as e:
            logging.error(f"Ошибка БД при профиле: {e}")
            await message.reply("❌ Ошибка базы данных при загрузке профиля.")

# --- ОБРАБОТКА КНОПОК ---
@router.callback_query(F.data.startswith("accept_rel_"))
async def process_accept_rel(callback: CallbackQuery, db: asyncpg.Pool):
    data = callback.data.split("_")
    initiator_id = int(data[2])
    target_id = int(data[3])
    
    try:
        await db.execute(
            "INSERT INTO couples (chat_id, user1_id, user2_id, sparks, level) VALUES ($1, $2, $3, 100, 1)",
            callback.message.chat.id, initiator_id, target_id
        )
            
        await callback.message.edit_text(
            f"💖 Отношения заключены!\n"
            f"Пара получает <b>100 искр</b>.\n"
            f"Напишите `.отн я`, чтобы посмотреть профиль."
        )
        await callback.answer("Отношения созданы!")
    except Exception as e:
        logging.error(f"Ошибка БД при создании пары: {e}")
        await callback.answer("Ошибка БД", show_alert=True)

@router.callback_query(F.data == "decline_rel")
async def process_decline_rel(callback: CallbackQuery):
    await callback.message.edit_text("💔 Предложение отношений отклонено.")
    await callback.answer()

# --- ЗАГЛУШКИ ---
@router.callback_query(F.data.in_({"buy_sparks", "buy_premium", "menu_children", "menu_pregnancy", "menu_house", "menu_pets", "menu_gifts", "menu_history"}))
async def profile_menus(callback: CallbackQuery):
    await callback.answer("Этот раздел находится в разработке.", show_alert=True)
