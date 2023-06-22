import sqlite3

import datetime
import logging
import time
import json
import pprint
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from environs import Env

from sql_functions import (
    SQL_register_new_user,
    SQL_get_user_data,
    SQL_put_user_phone,
    SQL_add_new_order)


logging.basicConfig(filename='bot.log', level=logging.INFO)


env = Env()
env.read_env(override=True)
token = '5778281282:AAHAPOtzeP7_qofFxkkb0KxgSJzhMarWn-Y'
bot = telebot.TeleBot(token)
pp = pprint.PrettyPrinter(indent=4)


def calculate_order_cost(weight, capacity, duration):
    cost = 15*(weight*0.75 + capacity*0.6)*duration
    return int(cost)


def print_order_text(order: dict):

    text = '\n\n'
    text += "Данные заказа:\n"
    if order:
        for key, value in order.items():
            if key == 'duration' and value:
                text += f'Длительность аренды - {value} мес\n'
            if key == 'capacity' and value:
                text += f'Объём - {value} куб.метров\n'
            if key == 'weight' and value:
                text += f'Вес - {value} килограмм\n'
            if key == 'measure_later' and value:
                text += "Вес и объём - уточним позднее\n"
            if key == 'measure_later' and not value and 'order_cost' in order.keys():
                text += f"Примерная стоимость аренды - {order['order_cost']} руб.\n"
            if key == 'delivery':
                text += 'Доставка - нужна\n' if value else 'Доставка - самостоятельно\n'
                if 'address' in order.keys() and value:
                    text += f"Адрес от куда забрать: {order['address']}\n"
            if key == 'begining_day':
                text += f"Дата начала аренды: {value}\n"
            if key == 'delivery_hour':
                text += f"Время для доставки: {value}:00\n"
            if key == 'contact_phone':
                text += f"Контактный номер: {value}\n"

    return text


@bot.message_handler(commands=['start'])
def send_welcome(message):

    user_tg_id = message.from_user.id
    user_name = message.from_user.full_name
    user_login = message.from_user.username
    if not user_name:
        user_name = user_login

    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("ПРИНИМАЮ >>", callback_data="main_page"))

    user = SQL_get_user_data(user_tg_id)

    if user:    # Если не новый пользователь
        start_text = f"С возвращением! {user['name']}.\n Т.к. Вас давно небыло, то убедитесь пожалуйста, что Вы по прежнему принимаете наши условия обработки данных и политику безопасности. Ознакомиться можно по этой ссылке"
        bot.send_message(
            message.chat.id,
            start_text,
            reply_markup=markup
            )
    else:       # Если пользователь новый
        start_text = f"Привет, {user_name}!\nПрежде чем оформить заказ, давайте Вы разрешите нам пользоваться данными которые нам необходимо будет получить от Вас? \n \n Вот ссылка на текст соглашения, нажимая на кнопку продолжить - вы подтверждаете что ознакомились с нашими условиями и приняли их."
        bot.send_message(
            message.chat.id,
            start_text,
            reply_markup=markup
            )
        SQL_register_new_user(user_tg_id, user_name)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    user_tg_id = call.from_user.id
    user = SQL_get_user_data(user_tg_id)

    current_order = bot.__dict__['user_order'] if 'user_order' in bot.__dict__.keys() else {}
    wellcome_text = "Текст Wellcome-Page"

    if "main_page" in call.data:
        is_confirmed = call.data
        if is_confirmed.split("#")[-1] == 'confirmed':
            dialog_text = "Ваш заказ принят.\nСкоро, с Вами свяжутся наши менеджеры"
            dialog_text += print_order_text(current_order)
            bot.send_message(call.message.chat.id, dialog_text, reply_markup=ReplyKeyboardRemove())
            bot.delete_message(call.message.chat.id, call.message.id)
            call.message.id = bot.send_message(call.message.chat.id, wellcome_text).message_id
            for key in current_order.keys():
                if not current_order[key]:
                    current_order[key] = ''
            SQL_add_new_order(
                user_tg_id,
                current_order['begining_day'],
                duration=current_order['duration'],
                weight=current_order['weight'],
                capacity=current_order['capacity'],
                cost=current_order['order_cost'],
                delivery=current_order['delivery'],
                delivery_time=current_order['delivery_hour'],
                address=current_order['address']
                )
            del bot.__dict__['user_order']
            time.sleep(1)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button1 = InlineKeyboardButton('Арендовать место', callback_data='new_order')
        button2 = InlineKeyboardButton('Ознакомиться с подробностями', callback_data='show_info')
        button3 = InlineKeyboardButton('Мои Аренды', callback_data='show_orders')
        markup.add(button1, button2, button3)
        bot.edit_message_text(wellcome_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "new_order" in call.data:

        dialog_text = "Вы определили какой вес и объём Вам необходимо сдать на хранение...\nИли Вам потребуется наша помощь?"
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button1 = InlineKeyboardButton('Да, я знаю параметры', callback_data='order_measures#Have')
        button2 = InlineKeyboardButton('Нет, мы определим позднее', callback_data='order_duration#Later')
        button3 = InlineKeyboardButton('<< Назад', callback_data='main_page')
        markup.add(button1, button2, button3)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_measures" in call.data:

        measure_later = call.data
        if measure_later.split("#")[-1] == 'Have':
            current_order = {'measure_later': False}
        current_order.update({'last_message': call.message.id})
        bot.__dict__['user_order'] = current_order

        dialog_text = "Напишите в чат примерный объём для заказа\n(в кубических метрах)"

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button_pre = InlineKeyboardButton('<< Назад', callback_data='new_order')
        markup.add(button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, ask_capacity)

    if "order_duration" in call.data:

        measure_later = call.data
        if measure_later.split("#")[-1] == 'Later':
            current_order = {'measure_later': True}
            current_order.update({'weight': False})
            current_order.update({'capacity': False})
            current_order.update({'cost': False})
            bot.__dict__['user_order'] = current_order

        dialog_text = "На сколько месяцев Вам требуется аренда?"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row_width = 6
        button01 = InlineKeyboardButton('1', callback_data='order_delivery_needs#01')
        button02 = InlineKeyboardButton('2', callback_data='order_delivery_needs#02')
        button03 = InlineKeyboardButton('3', callback_data='order_delivery_needs#03')
        button04 = InlineKeyboardButton('4', callback_data='order_delivery_needs#04')
        button05 = InlineKeyboardButton('5', callback_data='order_delivery_needs#05')
        button06 = InlineKeyboardButton('6', callback_data='order_delivery_needs#06')
        button07 = InlineKeyboardButton('7', callback_data='order_delivery_needs#07')
        button08 = InlineKeyboardButton('8', callback_data='order_delivery_needs#08')
        button09 = InlineKeyboardButton('9', callback_data='order_delivery_needs#09')
        button10 = InlineKeyboardButton('10', callback_data='order_delivery_needs#10')
        button11 = InlineKeyboardButton('11', callback_data='order_delivery_needs#11')
        button12 = InlineKeyboardButton('12', callback_data='order_delivery_needs#12')
        button_pre = InlineKeyboardButton('<< Назад', callback_data="new_order")

        markup.row(button01, button02, button03, button04, button05, button06)
        markup.row(button07, button08, button09, button10, button11, button12)
        markup.row(button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_delivery_needs" in call.data:

        duration = call.data
        if duration.split("#")[-1]:
            duration_months = int(duration.split("#")[-1])
            current_order.update({'duration': duration_months})

        if 'weight' in current_order.keys():
            order_cost = calculate_order_cost(current_order['weight'], current_order['capacity'], current_order['duration'])
            current_order.update({'order_cost': order_cost})

        bot.__dict__['user_order'] = current_order

        dialog_text = "Вам помочь с доставкой, или Вы доставите вещи самостоятельно?"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button1 = InlineKeyboardButton('Да, организуйте доставку сами', callback_data='order_delivery_address#is_delivery')
        button2 = InlineKeyboardButton('Нет, я доставлю', callback_data='order_begining_month#not_delivery')
        button_pre = InlineKeyboardButton('<< Назад', callback_data="order_duration")
        markup.add(button1, button2, button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_delivery_address" in call.data:

        is_delivery = call.data
        if is_delivery.split("#")[-1] == 'is_delivery':
            current_order.update({'delivery': True})
            current_order.update({'last_message': call.message.id})
            bot.__dict__['user_order'] = current_order

        dialog_text = "Напишите в чат адрес, от куда надо будет забрать вещи."
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button_pre = InlineKeyboardButton('<< Назад', callback_data='order_delivery_needs#')
        markup.add(button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, ask_address)

    if "order_begining_month" in call.data:

        is_delivery = call.data
        if is_delivery.split("#")[-1] == 'not_delivery':
            current_order.update({'delivery': False})
            current_order.update({'address': False})
            bot.__dict__['user_order'] = current_order

        if 'last_message' in current_order.keys() and current_order['address']:
            bot.delete_message(call.message.chat.id, current_order['last_message'])
            del current_order['last_message']

        bot.__dict__['user_order'] = current_order

        dialog_text = "Определите месяц(начала аренды)"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        button01 = InlineKeyboardButton('Январь', callback_data='order_begining_day#1')
        button02 = InlineKeyboardButton('Февраль', callback_data='order_begining_day#2')
        button03 = InlineKeyboardButton('Март', callback_data='order_begining_day#3')
        button04 = InlineKeyboardButton('Апрель', callback_data='order_begining_day#4')
        button05 = InlineKeyboardButton('Май', callback_data='order_begining_day#5')
        button06 = InlineKeyboardButton('Июнь', callback_data='order_begining_day#6')
        button07 = InlineKeyboardButton('Июль', callback_data='order_begining_day#7')
        button08 = InlineKeyboardButton('Август', callback_data='order_begining_day#8')
        button09 = InlineKeyboardButton('Сентябрь', callback_data='order_begining_day#9')
        button10 = InlineKeyboardButton('Октябрь', callback_data='order_begining_day#10')
        button11 = InlineKeyboardButton('Ноябрь', callback_data='order_begining_day#11')
        button12 = InlineKeyboardButton('Декабрь', callback_data='order_begining_day#12')

        markup.row(button01, button02, button03, button04)
        markup.row(button05, button06, button07, button08)
        markup.row(button09, button10, button11, button12)
        markup.row(InlineKeyboardButton('<< Назад', callback_data='order_delivery_needs#'))

        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_begining_day" in call.data:

        begining_month = call.data
        if begining_month.split("#")[-1]:
            begining_month = int(begining_month.split("#")[-1])
            current_order.update({'begining_month': begining_month})
            bot.__dict__['user_order'] = current_order

        month = current_order['begining_month']
        current_year = datetime.datetime.now().year
        days_in_month = (datetime.date(current_year, month+1, 1)-datetime.date(current_year, month, 1)).days if month < 12 else 31
        buttons = []
        for day in range(days_in_month):
            buttons.append(InlineKeyboardButton(day+1, callback_data=f'order_delivery_time#{day+1}'))

        dialog_text = "Определите день(начала аренды)"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row(*buttons)
        markup.row(InlineKeyboardButton('<< Назад', callback_data='order_begining_month'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_delivery_time" in call.data:

        begining_day = call.data
        if begining_day.split("#")[-1]:
            begining_day = int(begining_day.split("#")[-1])
            year = datetime.datetime.now().year
            today_date = datetime.date(datetime.datetime.now().year,
                         datetime.datetime.now().month,
                         datetime.datetime.now().day)
            date_delta = (datetime.date(year, current_order['begining_month'], begining_day) - today_date).days
            if date_delta < 1:
                year += 1

            current_order.update({'begining_day': f'{begining_day}.{current_order["begining_month"]}.{year}'})
            bot.__dict__['user_order'] = current_order

        if current_order['delivery']:
            dialog_text = "Выберите удобное Вам время, во сколько доставке забрать Ваши вещи"
        else:
            dialog_text = "Выберите ориентировочное время, во сколько Вы приедете к нам в день начала аренды"

        dialog_text += print_order_text(current_order)

        buttons1 = [InlineKeyboardButton(f'{hour+1}:00', callback_data=f'order_contact#{hour+1}') for hour in range(7, 11)]
        buttons2 = [InlineKeyboardButton(f'{hour+1}:00', callback_data=f'order_contact#{hour+1}') for hour in range(11, 15)]
        buttons3 = [InlineKeyboardButton(f'{hour+1}:00', callback_data=f'order_contact#{hour+1}') for hour in range(15, 19)]
        buttons4 = [InlineKeyboardButton(f'{hour+1}:00', callback_data=f'order_contact#{hour+1}') for hour in range(19, 23)]

        markup = InlineKeyboardMarkup()
        markup.row(*buttons1)
        markup.row(*buttons2)
        markup.row(*buttons3)
        markup.row(*buttons4)
        markup.row(InlineKeyboardButton('<< Назад', callback_data='order_begining_day#'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "order_contact" in call.data:
        delivery_hour = call.data
        if delivery_hour.split("#")[-1]:
            delivery_hour = int(delivery_hour.split("#")[-1])
            current_order.update({'delivery_hour': delivery_hour})
            bot.__dict__['user_order'] = current_order

        if user['phone']:
            dialog_text = "Осталось определиться с контактными данными.\n"
            dialog_text += "Отправьте в чат контактный номер.\n"
            dialog_text += "Или нажмите на кнопку, если прошлый номер по-прежнему актуальный"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"Да, прежний:\n{user['phone']}", callback_data='order_resume#last_phone'))
            markup.add(InlineKeyboardButton('<< Назад', callback_data='order_delivery_time#'))
            bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        else:
            dialog_text = "Осталось определиться с контактными данными.\n"
            dialog_text += "Отправьте в чат контактный номер.\n"
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(text='предать боту свой ТГ номер телефона', request_contact=True))
            bot.send_message(call.message.chat.id, dialog_text, reply_markup=markup)

    if "order_resume" in call.data:

        last_phone = call.data
        if last_phone.split("#")[-1] == 'last_phone':
            current_order.update({'contact_phone': user['phone']})
        bot.__dict__['user_order'] = current_order

        dialog_text = "Подтвердите данные оставленные в заявке.\n(наши менеджеры свяжутся с Вами сразу как данные будут обработанны)"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('Да, всё верно', callback_data='main_page#confirmed'))
        markup.add(InlineKeyboardButton('<< Назад', callback_data='order_contact#'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)


@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    bot.delete_message(message.chat.id, message.message_id)
    user_tg_id = message.from_user.id
    new_message = bot.send_message(message.chat.id, "Клавиатура скрыта.", reply_markup=ReplyKeyboardRemove()).message_id
    bot.delete_message(message.chat.id, new_message)
    bot.clear_step_handler_by_chat_id(message.chat.id)

    SQL_put_user_phone(user_tg_id, message.contact.phone_number)

    bot.send_message(
        message.chat.id,
        message.contact.phone_number,
        reply_markup=InlineKeyboardMarkup(keyboard=[[InlineKeyboardButton(text="Далее >>", callback_data="order_resume#last_phone")]])
        )


def catch_messages(message):
    True


def ask_address(message):
    if message.text:
        current_order = bot.__dict__['user_order']
        current_order.update({'delivery': True})
        current_order.update({'address': message.text})
        bot.__dict__['user_order'] = current_order
        bot.send_message(
            message.chat.id,
            message.text,
            reply_markup=InlineKeyboardMarkup(keyboard=[[InlineKeyboardButton(text="Далее >>", callback_data="order_begining_month")]])
            )


def ask_capacity(message):
    if message.text:

        current_order = bot.__dict__['user_order']
        current_order.update({'capacity': float(message.text)})

        dialog_text = "Теперь отправьте в чат общий вес(в килограммах)"
        last_message_2 = bot.send_message(message.chat.id, dialog_text).message_id
        bot.register_next_step_handler(message, ask_weight)

        current_order.update({'last_message_2': last_message_2})
        bot.__dict__['user_order'] = current_order


def ask_weight(message):
    if message.text:
        current_order = bot.__dict__['user_order']
        current_order.update({'weight': float(message.text)})

        dialog_text = f"Объём: {current_order['capacity']} куб.метров\n"
        dialog_text += f"Вес: {current_order['weight']} килограмм\n"

        new_id = bot.send_message(
                    message.chat.id,
                    dialog_text,
                    reply_markup=InlineKeyboardMarkup(keyboard=[[InlineKeyboardButton(text="Далее >>", callback_data="order_duration")]])
                    ).message_id

        current_order.update({'new_message': new_id})
        bot.__dict__['user_order'] = current_order


def main():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as error:
            print(error)
            time.sleep(5)


if __name__ == '__main__':
    main()
