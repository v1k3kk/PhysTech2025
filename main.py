# --- Telegram FitTrack Bot ---
# Этот бот позволяет пользователям отслеживать тренировки, устанавливать напоминания, управлять прогрессом и настройками.

# Импорт необходимых библиотек
import json
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import re
from datetime import datetime
import asyncio

# Токен бота 
TOKEN = "api"

# Запуск планировщика задач
scheduler = BackgroundScheduler()
scheduler.start()

# Загрузка и сохранение данных пользователей из/в JSON файл
def load_user_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_user_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DATA_FILE = "user_data.json"

# Глобальное хранилище данных пользователей
user_data_store = load_user_data()

# Переменные для доступа к боту и главному event loop
bot_instance = None  

# Главное меню (reply клавиатура)
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🏋️‍♂️ Тренировка"), KeyboardButton("🧠 Прогресс")],
        [KeyboardButton("⏰ Напоминания"), KeyboardButton("🍽 Питание")],
        [KeyboardButton("🎯 Моя цель"), KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Команда /start — инициализация профиля и меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_data_store:
        user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": 0}
        save_user_data(user_data_store)
    await update.message.reply_text(
        "🏁 Добро пожаловать в FitTrack!\nВыберите действие из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )

# Обработка кнопки "Тренировка" — запись активности в историю
async def handle_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    workout_text = "🏋️‍♂️ Вы выбрали тренировку. Что будем качать сегодня?"
    user_data_store.setdefault(user_id, {"reminders": [], "workouts": [], "timezone": 0})
    user_data_store[user_id]["workouts"].append({"date": datetime.now().isoformat(), "note": "Выбрана тренировка"})
    save_user_data(user_data_store)
    await update.message.reply_text(workout_text)

# Обработка кнопки "Прогресс"
async def handle_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    progress_text = "📊 Вот ваш прогресс. Продолжайте в том же духе!"
    await update.message.reply_text(progress_text)

# Обработка кнопки "Напоминания" — показ меню с inline-кнопками
async def handle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Установить время", callback_data="reminder_time_select")],
        [InlineKeyboardButton("📋 Список", callback_data="reminder_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⏰ Управление напоминаниями:", reply_markup=reply_markup)

# Обработка кнопки "Питание"
async def handle_nutrition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🍽 Вот ваш план питания на сегодня.")

# Обработка кнопки "Моя цель"
async def handle_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Выберите цель: похудение, набор массы или поддержание формы.")

# Обработка кнопки "Настройки"
async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Настройки профиля. Здесь можно сбросить данные или поменять язык.")

# Отправка напоминания (вызывается из планировщика APScheduler)
def send_reminder(reminder_context):
    chat_id = reminder_context["chat_id"]
    import asyncio
    global main_loop, bot_instance
    if main_loop and not main_loop.is_closed():
        main_loop.call_soon_threadsafe(
            asyncio.create_task,
            bot_instance.send_message(chat_id=chat_id, text="Привет. Ты просил тебе напомнить о чем-то очень важном!")
        )

# Обработка inline-кнопок (установка времени, просмотр/удаление напоминаний)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in user_data_store:
        user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": 0}
        save_user_data(user_data_store)
    if query.data == "reminder_time_select":
        await query.edit_message_text("🕒 Введите время в формате HH:MM или дату и время в формате DD.MM HH:MM")
        context.user_data["awaiting_reminder_time"] = True
    elif query.data == "reminder_list":
        reminders = user_data_store[user_id].get("reminders", [])
        if not reminders:
            await query.edit_message_text("🔕 У вас нет активных напоминаний.")
        else:
            message = "📋 Ваши напоминания:\n"
            keyboard = []
            for i, rem in enumerate(reminders):
                if rem["type"] == "daily":
                    label = f"{i+1}) Ежедневно в {rem['hour']:02d}:{rem['minute']:02d}"
                else:
                    label = f"{i+1}) Один раз: {rem['datetime']}"
                message += f"{label}\n"
                keyboard.append([InlineKeyboardButton(f"❌ Удалить {i+1}", callback_data=f"reminder_delete_{i}")])
            markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=markup)
    elif query.data.startswith("reminder_delete_"):
        index = int(query.data.split("_")[-1])
        reminders = user_data_store[user_id].get("reminders", [])
        if 0 <= index < len(reminders):
            rem = reminders.pop(index)
            save_user_data(user_data_store)
            try:
                scheduler.remove_job(rem.get("job_id"))
            except Exception:
                pass
            await query.edit_message_text("🗑 Напоминание удалено.")
        else:
            await query.edit_message_text("❌ Напоминание не найдено.")

# Обработка текстового ввода времени от пользователя
async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_reminder_time"):
        text = update.message.text.strip()
        date_match = re.match(r"^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})$", text)
        time_match = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", text)
        user_id = str(update.effective_user.id)
        tz = user_data_store.get(user_id, {}).get("timezone", 0)

        if user_id not in user_data_store:
            user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": tz}
            save_user_data(user_data_store)

        if date_match:
            day, month, hour, minute = map(int, date_match.groups())
            now = datetime.now()
            run_date = datetime(year=now.year, month=month, day=day, hour=hour, minute=minute)
            run_date = run_date.replace(hour=(run_date.hour - tz) % 24)
            context.user_data["pending_reminder"] = ("once", run_date)
            await update.message.reply_text(f"❓ Установить одноразовое напоминание на {run_date.strftime('%d.%m %H:%M')}? (Да/Нет)")
        elif time_match:
            hour, minute = map(int, time_match.groups())
            hour = (hour - tz) % 24
            context.user_data["pending_reminder"] = ("daily", (hour, minute))
            await update.message.reply_text(f"❓ Установить ежедневное напоминание на {hour:02d}:{minute:02d}? (Да/Нет)")
        else:
            await update.message.reply_text("❌ Неверный формат. Используй HH:MM или DD.MM HH:MM")
        context.user_data["awaiting_reminder_time"] = False

# Подтверждение установки напоминания (Да / Нет)
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if update.message.text.lower() == "да" and "pending_reminder" in context.user_data:
        chat_id = update.effective_chat.id
        kind, value = context.user_data.pop("pending_reminder")
        if user_id not in user_data_store:
            user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": 0}
        if kind == "once":
            job = scheduler.add_job(send_reminder, 'date', run_date=value, args=[{"chat_id": chat_id}], id=f"reminder_once_{chat_id}_{value.timestamp()}")
            user_data_store[user_id]["reminders"].append({"type": "once", "datetime": value.strftime('%Y-%m-%d %H:%M:%S'), "job_id": job.id})
        else:
            hour, minute = value
            job = scheduler.add_job(send_reminder, 'cron', hour=hour, minute=minute, args=[{"chat_id": chat_id}], id=f"reminder_{chat_id}_{hour}_{minute}")
            user_data_store[user_id]["reminders"].append({"type": "daily", "hour": hour, "minute": minute, "job_id": job.id})
        save_user_data(user_data_store)
        await update.message.reply_text("✅ Напоминание установлено.")
    elif update.message.text.lower() == "нет":
        context.user_data.pop("pending_reminder", None)
        await update.message.reply_text("❌ Напоминание отменено.")

# Установка часового пояса пользователем (командой или текстом)
async def handle_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    match = re.match(r"^tz\s*([+-]?\d{1,2})$", text)
    user_id = str(update.effective_user.id)
    if match:
        offset = int(match.group(1))
        if user_id not in user_data_store:
            user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": 0}
        user_data_store[user_id]["timezone"] = offset
        save_user_data(user_data_store)
        await update.message.reply_text(f"🌍 Часовой пояс установлен: GMT{offset:+}")

# Установка часового пояса пользователем (командой или текстом)
async def handle_timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if context.args:
        try:
            offset = int(context.args[0])
            if user_id not in user_data_store:
                user_data_store[user_id] = {"reminders": [], "workouts": [], "timezone": 0}
            user_data_store[user_id]["timezone"] = offset
            save_user_data(user_data_store)
            await update.message.reply_text(f"🌍 Часовой пояс установлен: GMT{offset:+}")
        except:
            await update.message.reply_text("❌ Неверный формат. Используй /tz +2 или /tz -3")
    else:
        await update.message.reply_text("📌 Введите смещение, например: /tz +2")

# Запуск бота и регистрация всех обработчиков
def run_bot():
    global bot_instance, main_loop
    app = Application.builder().token(TOKEN).build()
    bot_instance = app.bot
    main_loop = asyncio.get_event_loop()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tz", handle_timezone_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🏋️‍♂️ Тренировка"), handle_workout))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🧠 Прогресс"), handle_progress))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("⏰ Напоминания"), handle_reminders))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🍽 Питание"), handle_nutrition))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🎯 Моя цель"), handle_goal))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("⚙️ Настройки"), handle_settings))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^tz\s*[+-]?\d{1,2}$"), handle_timezone))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^(да|нет)$"), handle_confirmation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("✅ Bot started")
    app.run_polling()

# Запуск main функции
if __name__ == "__main__":
    run_bot()