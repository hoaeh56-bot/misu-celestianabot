# relationship.py
import asyncpg
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging

router = Router()

# --- КОМАНДА .мойпол (ловит любой текст с "пол") ---
@router.message(F.text.lower().contains("мой"))
async def set_gender(message: Message, db: asyncpg.Pool):
    text = message.text.lower()
    if "пол" not in text:
        return

    if text.endswith("м") or " м" in text:
        gender = "м"
    elif text.endswith("ж") or " ж" in text:
        gender = "ж"
    else:
        await message.reply("⚠️ Укажи пол: .мойпол м или .мойпол ж")
        return
    
    await db.execute(
        "INSERT INTO users (user_id, username, gender) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET gender = EXCLUDED.gender",
        message.from_user.id, message.from_user.username, gender
    )
    await message.reply(f"✅ Твой пол установлен: {'Мужской' if gender == 'м' else 'Женский'}.")

# --- ГЛАВНЫЙ ОБРАБОТЧИК .отн ---
@router.message(F.text.lower().startswith(".отн"))
async def relationship_handler(message: Message, db: asyncpg.Pool):
    text = message.text.lower()
    args = text.split()
    
    # Если написали просто .отн или .отн (без аргументов) - показываем меню
    if len(args) == 1 or args[1] not in ["пара", "создать", "запрос", "я"]:
        menu_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Создать пару", callback_data="show_create_info")],
            [InlineKeyboardButton(text="🔥 Предложить секс", callback_data="show_sex_info")],
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="show_profile_info")]
        ])
        await message.reply(
            "💖 <b>Меню отношений</b>\n"
            "Выбери действие или напиши команду:\n"
            "• `.отн пара` (ответом на сообщение) — создать пару\n"
            "• `.отн запрос` (ответом на сообщение) — предложить секс\n"
            "• `.отн я` — посмотреть профиль",
            reply_markup=menu_kb
        )
        return

    action = args[1]

    # --- .отн пара ---
    if action in ["пара", "создать"]:
        if not message.reply_to_message:
            await message.reply("💔 Ответь (Reply) на сообщение человека, с которым хочешь начать отношения.")
            return
        
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        initiator_id = message.from_user.id
        initiator_name = message.from_user.first_name
        
        if target_id == initiator_id:
            await message.reply("🤨 Нельзя вступить в отношения с самим собой.")
            return

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

    # --- .отн запрос (СЕКС) ---
    elif action == "запрос":
        if not message.reply_to_message:
            await message.reply("🔥 Ответь (Reply) на сообщение человека, которому хочешь предложить секс.")
            return
        
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name
        initiator_name = message.from_user.first_name
        
        if target_id == message.from_user.id:
            await message.reply("🤨 Сам с собой? Иди поработай.")
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Да", callback_data=f"accept_sex_{message.from_user.id}_{target_id}"),
             InlineKeyboardButton(text="❌ Нет", callback_data="decline_sex")]
        ])
        
        await message.reply(
            f"🔥 <b>{target_name}</b>, есть предложение!\n"
            f"<b>{initiator_name}</b> хочет заняться с тобой сексом.\n"
            f"Ответишь?",
            reply_markup=kb
        )

    # --- .отн я (РАСШИРЕННЫЙ ПРОФИЛЬ) ---
    elif action == "я":
        couple = await db.fetchrow(
            "SELECT * FROM couples WHERE chat_id = $1 AND status = 'ACTIVE' AND (user1_id = $2 OR user2_id = $2)",
            message.chat.id, message.from_user.id
        )
        
        if not couple:
            await message.reply("❌ У тебя пока нет пары в этом чате. Используй `.отн пара`.")
            return

        partner_id = couple['user2_id'] if couple['user1_id'] == message.from_user.id else couple['user1_id']
        partner = await db.fetchrow("SELECT username FROM users WHERE user_id = $1", partner_id)
        
        # Формируем ники и ссылки
        my_username = message.from_user.username or "нет_ника"
        partner_username = partner['username'] if partner and partner['username'] else "нет_ника"
        
        my_link = f"<a href='https://t.me/{my_username}'>{my_username}</a>" if my_username != "нет_ника" else "Скрыт"
        partner_link = f"<a href='https://t.me/{partner_username}'>{partner_username}</a>" if partner_username != "нет_ника" else "Скрыт"

        # Заглушки для счетчиков (потом сделаем реальные таблицы)
        hugs = 0
        kisses = 0
        sex_count = 0
        children_count = 0

        profile_text = (
            f"❤️ <b>Информация о паре</b>\n\n"
            f"👤 <b>Ты:</b> {my_link}\n"
            f"👤 <b>Партнер:</b> {partner_link}\n"
            f"🆔 ID отношений: {couple['id']}\n\n"
            f"💎 <b>Искры:</b> {couple['sparks']}\n"
            f"📈 <b>Уровень:</b> {couple['level']}\n"
            f"🏠 <b>Дом:</b> Уютная квартира\n"
            f"👶 <b>Дети:</b> {children_count}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"🤗 Обнимашки: {hugs}\n"
            f"💋 Поцелуи: {kisses}\n"
            f"🔥 Секс: {sex_count}\n\n"
            f"<i>Искры тратятся на ежедневное содержание пары. Если упадут до 0 — отношения распадутся.</i>"
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
        
        await message.reply(profile_text, reply_markup=kb, disable_web_page_preview=True)

# --- ОБРАБОТКА КНОПОК ОТНОШЕНИЙ ---
@router.callback_query(F.data.startswith("accept_rel_"))
async def process_accept_rel(callback: CallbackQuery, db: asyncpg.Pool):
    data = callback.data.split("_")
    initiator_id = int(data[2])
    target_id = int(data[3])
    
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

@router.callback_query(F.data == "decline_rel")
async def process_decline_rel(callback: CallbackQuery):
    await callback.message.edit_text("💔 Предложение отношений отклонено.")
    await callback.answer()

# --- ОБРАБОТКА КНОПОК СЕКСА ---
@router.callback_query(F.data.startswith("accept_sex_"))
async def process_accept_sex(callback: CallbackQuery, db: asyncpg.Pool):
    await callback.message.edit_text(
        f"🔥 Вы занялись сексом!\n"
        f"<i>(Пока это просто текст, потом добавим генерацию картинок или начисление искр)</i>"
    )
    await callback.answer("Успехов! 🔥")

@router.callback_query(F.data == "decline_sex")
async def process_decline_sex(callback: CallbackQuery):
    await callback.message.edit_text("❌ В сексе отказано. Не судьба.")
    await callback.answer()

# --- ЗАГЛУШКИ ДЛЯ КНОПОК МЕНЮ ---
@router.callback_query(F.data.in_({"buy_sparks", "buy_premium", "menu_children", "menu_pregnancy", "menu_house", "menu_pets", "menu_gifts", "menu_history", "show_create_info", "show_sex_info", "show_profile_info"}))
async def profile_menus(callback: CallbackQuery):
    await callback.answer("Этот раздел находится в разработке.", show_alert=True)
