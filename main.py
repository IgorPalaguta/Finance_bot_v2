import telebot
import sqlite3

from datetime import datetime
from telebot import types
import pytesseract
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from PIL import Image
import re
import io

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

bot = telebot.TeleBot('7882507904:AAG3bvuxPQYhxfDrLR3MFEPgssHbnoQ4J_s')

# Підключення до бази даних
conn = sqlite3.connect('expenses.db', check_same_thread=False)
cursor = conn.cursor()

# Оновлене створення таблиць
cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    category TEXT,
                    date TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    UNIQUE(user_id, name),
                    FOREIGN KEY (user_id) REFERENCES users(id))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS budgets (
                    user_id INTEGER PRIMARY KEY,
                    amount REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id))''')

conn.commit()

# Тимчасове зберігання даних користувачів
user_data = {}


def get_user_id(telegram_id):
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    if user:
        return user[0]
    cursor.execute("INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,))
    conn.commit()
    return cursor.lastrowid


def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_webapp = KeyboardButton("🌐 Відкрити веб-застосунок", web_app=WebAppInfo(url="https://finance-bot-v2.onrender.com"))
    markup.add(btn_webapp)
    return markup

def start(update, context):
    user = update.effective_user
    init_data = update.callback_query.message.chat.id  # ID користувача

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Відкрити Web App", url=f"https://finance-bot-v2.onrender.com?user_id={user.id}")]
    ])
    
    context.bot.send_message(chat_id=user.id, text="Відкрийте веб-застосунок:", reply_markup=button)

@bot.message_handler(func=lambda message: message.text in ["➕ Додати витрату", "📊 Статистика", "➕ Додати категорію", "💰 Створити бюджет", "💰 Залишок бюджету", "ℹ️ Допомога"])
def handle_buttons(message):
    if message.text == "➕ Додати витрату":
        add_expense(message)
    elif message.text == "📊 Статистика":
        view_stats(message)
    elif message.text == "➕ Додати категорію":
        add_category(message)
    elif message.text == "💰 Створити бюджет":
        set_budget(message)
    elif message.text == "💰 Залишок бюджету":
        check_budget(message)  # Викликаємо функцію перевірки залишку бюджету
    elif message.text == "ℹ️ Допомога":
        bot.send_message(message.chat.id, "ℹ️ Доступні команди:\n"
                                          "/add - додати витрату\n"
                                          "/stats - переглянути статистику\n"
                                          "/addcategory - додати категорію\n"
                                          "/budget - перевірити залишок бюджету\n"
                                          "/start - головне меню")


@bot.message_handler(func=lambda message: message.text == "💰 Залишок бюджету")
def handle_budget_balance(message):
    check_budget(message)

@bot.message_handler(func=lambda message: message.text == "💰 Створити бюджет")
def set_budget(message):
    bot.send_message(message.chat.id, "Введіть розмір вашого бюджету на місяць:")
    bot.register_next_step_handler(message, save_budget)

def save_budget(message):
    try:
        amount = float(message.text.replace(',', '.'))
        user_id = get_user_id(message.chat.id)
        cursor.execute("INSERT INTO budgets (user_id, amount) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET amount = excluded.amount",(user_id, amount))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Бюджет встановлено: {amount} грн")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Будь ласка, введіть коректну суму.")

@bot.message_handler(commands=['start'])
def start_message(message):
    get_user_id(message.chat.id)
    bot.send_message(message.chat.id, "Вас вітає бот фінансового моніторингу! Виберіть дію:", reply_markup=main_menu())


@bot.message_handler(commands=['add'])
def add_expense(message):
    get_user_id(message.chat.id)
    bot.send_message(message.chat.id, "Введіть суму витрат:")
    bot.register_next_step_handler(message, get_amount)


def update_budget(user_id, amount):
    cursor.execute("SELECT amount FROM budgets WHERE user_id = ?", (user_id,))
    budget = cursor.fetchone()

    if budget:
        new_budget = budget[0] - amount
        cursor.execute("UPDATE budgets SET amount = ? WHERE user_id = ?", (new_budget, user_id))
        conn.commit()


def get_amount(message):
    try:
        amount = float(message.text.replace(',', '.'))
        user_id = get_user_id(message.chat.id)
        user_data[message.chat.id] = {'amount': amount}

        # Перевіряємо, чи є бюджет
        cursor.execute("SELECT amount FROM budgets WHERE user_id = ?", (user_id,))

        budget = cursor.fetchone()
        if budget and budget[0] < amount:
            bot.send_message(message.chat.id, "⚠️ Ваш бюджет недостатній для цієї витрати!")
            return

        cursor.execute("SELECT name FROM categories WHERE user_id = ?", (user_id,))
        categories = [row[0] for row in cursor.fetchall()]

        if not categories:
            bot.send_message(message.chat.id, "❌ У вас ще немає категорій! Додайте нову командою /addcategory")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("🔙 Назад до меню"))

        bot.send_message(message.chat.id, "Виберіть категорію витрат:", reply_markup=markup)
        bot.register_next_step_handler(message, get_category)
    except ValueError:
        bot.send_message(message.chat.id, "Будь ласка, введіть коректну суму.")


def get_category(message):
    if message.text == "🔙 Назад до меню":
        bot.send_message(message.chat.id, "🔸 Оберіть дію:", reply_markup=main_menu())
        return

    user_id = get_user_id(message.chat.id)
    category = message.text
    amount = user_data[message.chat.id]['amount']
    date = datetime.now().strftime('%Y-%m-%d')

    cursor.execute("INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
                   (user_id, amount, category, date))
    conn.commit()

    # Оновлюємо бюджет
    update_budget(user_id, amount)

    # Отримуємо залишок бюджету
    remaining_budget = get_budget_balance(user_id)

    if remaining_budget is not None:
        bot.send_message(message.chat.id,
                         f"✅ Додано витрати: {amount} грн на {category}\n💰 Залишок бюджету: {remaining_budget:.2f} грн",
                         reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, f"✅ Додано витрати: {amount} грн на {category}", reply_markup=main_menu())

    user_data.pop(message.chat.id, None)


@bot.message_handler(commands=['budget'])
def check_budget(message):
    user_id = get_user_id(message.chat.id)
    remaining_budget = get_budget_balance(user_id)

    if remaining_budget is not None:
        bot.send_message(message.chat.id, f"💰 Ваш залишок бюджету: {remaining_budget:.2f} грн")
    else:
        bot.send_message(message.chat.id, "❌ Ви ще не встановили бюджет! Скористайтеся кнопкою \"💰 Створити бюджет\".")


@bot.message_handler(commands=['addcategory'])
def add_category(message):
    bot.send_message(message.chat.id, "Введіть назву нової категорії:")
    bot.register_next_step_handler(message, save_category)


def save_category(message):
    user_id = get_user_id(message.chat.id)
    category_name = message.text.strip()
    if category_name:
        try:
            cursor.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (user_id, category_name))
            conn.commit()
            bot.send_message(message.chat.id, f"Категорія '{category_name}' додана успішно! ✅")
        except sqlite3.IntegrityError:
            bot.send_message(message.chat.id, f"Категорія '{category_name}' вже існує! ⚠️")
    else:
        bot.send_message(message.chat.id, "Категорія не може бути порожньою. Спробуйте ще раз.")


@bot.message_handler(commands=['stats'])
def view_stats(message):
    user_id = get_user_id(message.chat.id)
    cursor.execute(
        "SELECT date, category, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY date, category ORDER BY date DESC",
        (user_id,))
    stats = cursor.fetchall()
    if stats:
        response = "📊 Статистика витрат:\n"
        current_date = None
        for date, category, total in stats:
            if date != current_date:
                current_date = date
                response += f"\n📅 {current_date}:\n"
            response += f"   {category}: {total} грн\n"
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "ℹ️ Ще немає записів про витрати.")

def get_budget_balance(user_id):
    cursor.execute("SELECT amount FROM budgets WHERE user_id = ?", (user_id,))
    budget = cursor.fetchone()
    return budget[0] if budget else None


bot.polling(non_stop=True)
