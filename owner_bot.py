import sqlite3
import telebot

from telebot import types
from environs import Env


env = Env()
env.read_env(override=True)
bot = telebot.TeleBot(env.str("TELEGRAM_OWNER_BOT_API_TOKEN"))

ADMIN_IDS = ["any"]


def db_advertising():
    connect = sqlite3.connect('selfstorage.db')
    cursor = connect.cursor()
    order_str = cursor.execute(f"SELECT * FROM orders WHERE address='на деревню дедушке'").fetchall()
    cursor.close()
    return str(len(order_str))


def db_orders_list():
    connect = sqlite3.connect('selfstorage.db')
    cursor = connect.cursor()
    cursor.execute('select * from orders;')
    records = cursor.fetchall()
    cursor.close()
    return records


def db_order_complete():
    connect = sqlite3.connect('selfstorage.db')
    cursor = connect.cursor()
    records = cursor.execute(f"SELECT * FROM orders WHERE weight=20").fetchall()
    for row in records:
        return f"Адрес: {str(row[9])}, номер телефона: {str(row[6])}"
    cursor.close()


def db_orders_overdue():
    connect = sqlite3.connect('selfstorage.db')
    cursor = connect.cursor()
    records = cursor.execute(f"SELECT * FROM orders WHERE end_date='data'").fetchall()
    cursor.close()
    return records


@bot.message_handler(commands=['start'])
def button_message(message):
    if message.from_user.id in ADMIN_IDS or "any" in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup(row_width=1)
        orders_advertising = types.InlineKeyboardButton("Заказы с рекламы", callback_data='advertising')
        orders_list = types.InlineKeyboardButton("Список заказов", callback_data='orders_list')
        order_complete = types.InlineKeyboardButton("Выполнить заказ", callback_data='order_complete')
        orders_overdue = types.InlineKeyboardButton("Просроченные заказы", callback_data='orders_overdue')
        markup.add(orders_advertising, orders_list, order_complete, orders_overdue)
        bot.send_message(message.chat.id, 'выберите пункт меню:', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.message:
        if call.data == 'advertising':
            bot.send_message(call.message.chat.id, f'Количество заказов, полученных с рекламы: {db_advertising()}')
        elif call.data == 'orders_list':
            bot.send_message(call.message.chat.id, 'Список заказов:')
            for row in db_orders_list():
                bot.send_message(call.message.chat.id, f'Заказ: №{str(row[0])}, вес: {str(row[2])} от {str(row[4])}')
        elif call.data == 'order_complete':
            bot.send_message(call.message.chat.id, 'Укажите номер заказа:')
        elif call.data == 'orders_overdue':
            bot.send_message(call.message.chat.id, 'Просроченные заказы:')
            for row in db_orders_overdue():
                bot.send_message(call.message.chat.id, f'Заказ: №{str(row[0])}, вес: {str(row[2])} от {str(row[4])}')


@bot.message_handler(content_types=['text'])
def after_text(message):
    if message.text == '2':
        bot.send_message(message.from_user.id, f'{db_order_complete()}', )
    else:
        bot.send_message(message.from_user.id, 'Заказ уже выполнен.')


bot.infinity_polling()
