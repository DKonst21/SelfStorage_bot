import sqlite3
import datetime
import sys
import time
import signal
import telebot

from environs import Env
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from sql_functions import (
    SQL_register_new_user,
    SQL_get_user_data,
    SQL_put_user_phone,
    SQL_add_new_order
    )


env = Env()
env.read_env(override=True)
bot = telebot.TeleBot(env.str("TELEGRAM_CLIENT_BOT_API_TOKEN"))


def signal_handler(signum, frame):
    sys.exit(0)


def calculate_order_cost(weight, capacity, duration):
    cost = 15*(weight*0.75 + capacity*0.6)*duration
    return int(cost)


signal.signal(signal.SIGINT, signal_handler)

ADRESS = "Adress"

MEETUP_TEXT = "Приветствую в чат боте сервиса по аренде складкского помещения для вещей."

EXAMPLES_INTRO_TEXT = "Ниже перечислены основные примеры испоьзования:"

EXAMPLES_OS_USE = [
    "Вы можете положить свой старый хлам, который жалко выбрасывать.",
    "Вы можете складировать достаточно объёмные сезонные предметы: велосипед, снегоуборочную машину и т.д.",
]

RULES_INTRO_TEXT = "Для склада существует ряд правил:"

RULES = [
    "Не использовать склад в злоумышленных целях",
    "Не обманывать работников склада в целях скрытно положить на хранение запрещённый предмет",
]

UNALLOWED_ITEMS = [
    "Жидкости",
    "Органические продукты",
    "Животных",
    "Химические реагенты",
    "Облучённые чрезмерной дозой радиации предметы",
    "Все прочие запрещённые для хранения предметы по УК РФ",
]

ALLOWED_ITEMS = [
    "Книги",
    "Бытовую технику",
    "Спортивный инвентарь",
    "Одежду",
    "Предметы роскоши",
]


def get_intro_message_text() -> str:
    return MEETUP_TEXT + "\n" + EXAMPLES_INTRO_TEXT + "\n" + "\n".join(EXAMPLES_OS_USE)


def get_rules_messages_texts() -> tuple[str, str, str]:
    main_rules = RULES_INTRO_TEXT + "\n" + "\n".join(RULES)
    allowed_items = "Разрешено сдавать на хранение:" + "\n" + "\n".join(ALLOWED_ITEMS)
    unallowed_items = "Запрещено сдавать на хранение:" + "\n" + "\n".join(UNALLOWED_ITEMS)
    return main_rules, allowed_items, unallowed_items


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


def checking_float(message):
    current_order = bot.__dict__['user_order'] if 'user_order' in bot.__dict__.keys() else None
    succesful_text = f"Вы ввели: {message.text}\nПодтвердите ввод или введите другое число"
    failed_text = "Повторите ввод\nкак в примере: 10.3"
    try:
        current_order.update({'user_input': float(message.text)})
        if float(message.text) > 0:
            bot.__dict__['user_order'] = current_order
            message2_id = bot.send_message(message.chat.id, succesful_text).message_id
        else:
            message2_id = bot.send_message(message.chat.id, failed_text).message_id
    except ValueError:
        message2_id = bot.send_message(message.chat.id, failed_text).message_id

    time.sleep(2)
    bot.delete_message(message.chat.id, message.message_id)
    time.sleep(2)
    bot.delete_message(message.chat.id, message2_id)
    bot.register_next_step_handler(message, checking_float)


def confirm_address(message):
    current_order = bot.__dict__['user_order'] if 'user_order' in bot.__dict__.keys() else None
    current_order.update({'address': message.text})
    bot.__dict__['user_order'] = current_order
    message2_id = bot.send_message(message.chat.id, f"Вы ввели: {message.text}\nПодтвердите ввод или введите другой адрес").message_id

    time.sleep(2)
    bot.delete_message(message.chat.id, message.message_id)
    time.sleep(2)
    bot.delete_message(message.chat.id, message2_id)
    bot.register_next_step_handler(message, confirm_address)


def confirm_phone(message):

    current_order = bot.__dict__['user_order']

    if message.content_type == 'contact':
        user_tg_id = message.from_user.id
        SQL_put_user_phone(user_tg_id, message.contact.phone_number)
        current_order.update({'contact_phone': message.contact.phone_number})
        message_text = message.contact.phone_number
    else:
        current_order.update({'contact_phone': message.text})
        message_text = message.text

    new_message = bot.send_message(message.chat.id, "Клавиатура скрыта.", reply_markup=ReplyKeyboardRemove()).message_id
    bot.delete_message(message.chat.id, new_message)
    bot.clear_step_handler_by_chat_id(message.chat.id)

    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    button1 = InlineKeyboardButton(text="Далее >>", callback_data="order_resume#")
    # button2 = InlineKeyboardButton(text="<< Ввести другой", callback_data="order_contact#")
    markup.add(button1)
    call = current_order['call']
    del current_order['call']

    bot.edit_message_text(message_text, call.message.chat.id, call.message.id, reply_markup=markup)
    bot.delete_message(message.chat.id, message.message_id)
    if 'last_message_id' in current_order.keys():
        bot.delete_message(message.chat.id, current_order['last_message_id'])
        del current_order['last_message_id']

    bot.__dict__['user_order'] = current_order


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    current_order = bot.__dict__['user_order'] if 'user_order' in bot.__dict__.keys() else None

    user_tg_id = call.from_user.id
    user = SQL_get_user_data(user_tg_id)

    if "main_page" in call.data:
        wellcome_text = "Текст Wellcome-Page"
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
                address=current_order['address'],
                phone=current_order['contact_phone']
                )
            if user['phone'] != current_order['contact_phone']:
                SQL_put_user_phone(user_tg_id, current_order['contact_phone'])
            del bot.__dict__['user_order']
            time.sleep(1)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button1 = InlineKeyboardButton('Арендовать место', callback_data='new_order')
        button2 = InlineKeyboardButton('Мои Аренды', callback_data='show_orders')
        button3 = InlineKeyboardButton('Мои Предметы', callback_data='show_items')
        button4 = InlineKeyboardButton('Забрать предмет', callback_data='chose_item')
        button5 = InlineKeyboardButton('Правила', callback_data='show_info')
        markup.add(button1, button2, button3, button4, button5)
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

        dialog_text = "Хорошо. Напишите в чат объём в кубических метрах (пример: 10.3)."
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button_1 = InlineKeyboardButton('Подтвердить объём >>', callback_data='order_weight')
        button_pre = InlineKeyboardButton('<< Назад', callback_data='new_order')
        markup.add(button_1, button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, checking_float)

    if "order_weight" in call.data:

        if 'user_input' in current_order.keys():
            current_order.update({'capacity': current_order['user_input']})
            del current_order['user_input']

        dialog_text = "Хорошо. Напишите в чат вес в килограммах (пример: 34.25)"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        button_1 = InlineKeyboardButton('Подтвердить вес >>', callback_data='order_duration')
        button_pre = InlineKeyboardButton('<< Назад', callback_data='order_measures')
        markup.add(button_1, button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, checking_float)

    if "order_duration" in call.data:

        if current_order:
            if 'user_input' in current_order.keys():
                current_order.update({'weight': current_order['user_input']})
                del current_order['user_input']

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
        button_accept = InlineKeyboardButton('Подтвертить адрес >>', callback_data='order_begining_month')
        button_pre = InlineKeyboardButton('<< Назад', callback_data='order_delivery_needs#')
        markup.add(button_accept, button_pre)
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, confirm_address)

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
        if current_order["delivery"]:
            markup.row(InlineKeyboardButton('<< Назад', callback_data='order_delivery_address#'))
        else:
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
        current_order.update({'call': call})
        delivery_hour = call.data
        if delivery_hour.split("#")[-1]:
            delivery_hour = int(delivery_hour.split("#")[-1])
            current_order.update({'delivery_hour': delivery_hour})

        if user['phone']:
            dialog_text = "Осталось определиться с контактными данными.\n"
            dialog_text += "Отправьте в чат контактный номер.\n"
            dialog_text += "Или нажмите на кнопку, если прошлый номер по-прежнему актуальный"
            markup_inline = InlineKeyboardMarkup()
            markup_inline.add(InlineKeyboardButton(f"Да, прежний:\n{user['phone']}", callback_data='order_resume#last_phone'))
            markup_inline.add(InlineKeyboardButton('<< Назад', callback_data='order_delivery_time#'))
            bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup_inline)
        else:
            dialog_text = "Осталось определиться с контактными данными.\n"
            dialog_text2 = "Отправьте в чат контактный номер.\n"
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(text='Предать ТГ номер телефона', request_contact=True))
            bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id)
            last_message_id = bot.send_message(call.message.chat.id, dialog_text2, reply_markup=markup).message_id
            current_order.update({'last_message_id': last_message_id})

        bot.register_next_step_handler(call.message, confirm_phone)
        bot.__dict__['user_order'] = current_order

    if "order_resume" in call.data:

        last_phone = call.data
        if last_phone.split("#")[-1] == 'last_phone':
            current_order.update({'contact_phone': user['phone']})
        bot.__dict__['user_order'] = current_order

        dialog_text = "Подтвердите данные оставленные в заявке.\n(наши менеджеры свяжутся с Вами сразу как данные будут обработанны)"
        if "order_cost" in current_order.keys() and current_order['order_cost'] > 0:
            dialog_text += f"\n\nОриентировочная стоимость аренды: {current_order['order_cost']}"
        dialog_text += print_order_text(current_order)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('Да, всё верно', callback_data='main_page#confirmed'))
        markup.add(InlineKeyboardButton('<< Назад', callback_data='order_contact#'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "show_info" in call.data:

        dialog_text = "\n\n".join(get_rules_messages_texts())
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(InlineKeyboardButton('<< Назад', callback_data='main_page'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "show_items" in call.data:

        items_ids = []

        connection = sqlite3.connect("./selfstorage.db")
        cursor = connection.cursor()
        items_ids = [str(item[0]) + " - " + str("в хранилище" if item[1]=="false" else "выводится/выведен из хранилища") for item in cursor.execute(f"SELECT order_id, revisited FROM orders WHERE user_id={call.from_user.id}").fetchall()]

        dialog_text = "Предметы:\n" + "\n".join(items_ids)
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(InlineKeyboardButton('<< Назад', callback_data='main_page'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)

    if "chose_item" in call.data:

        def get_id(message):
            try:
                current_order.update({'id': int(message.text)})
                bot.__dict__['user_order'] = current_order

                connection = sqlite3.connect("./selfstorage.db")
                cursor = connection.cursor()
                update_script = f"UPDATE orders SET revisited=\'true\' WHERE user_id=\'{call.from_user.id}\' AND order_id=\'{current_order['id']}\'"
                cursor.execute(update_script)
                connection.commit()

                bot.send_message(
                    call.message.chat.id,
                    f"Ваш QR код: {hash(str(call.from_user.id))}",
                )
            except ValueError:
                bot.send_message(
                    message.chat.id,
                    "Не могу понять число, повторите ввод как в примере: '32'",
                )

        current_order = {}
        bot.__dict__['user_order'] = current_order

        items_ids = []

        connection = sqlite3.connect("./selfstorage.db")
        cursor = connection.cursor()
        items_ids = [str(item[0]) + " - " + str("в хранилище" if item[1]=="false" else "выводится/выведена из хранилища") for item in cursor.execute(f"SELECT order_id, revisited FROM orders WHERE user_id={call.from_user.id} AND revisited=\'false\'").fetchall()]

        dialog_text = "Введите в чат номер предмета для удаления:\nНомера предметов в ваших хранилищах:\n\n" + "\n".join(items_ids)
        markup = InlineKeyboardMarkup()
        markup.row_width = 1
        markup.add(InlineKeyboardButton('Подтвердить ID предмета', callback_data='main_page'))
        markup.add(InlineKeyboardButton('<< Назад', callback_data='main_page'))
        bot.edit_message_text(dialog_text, call.message.chat.id, call.message.id, reply_markup=markup)
        bot.register_next_step_handler(call.message, get_id)


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


def main():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as error:
            print(error)
            time.sleep(5)


if __name__ == '__main__':
    main()
