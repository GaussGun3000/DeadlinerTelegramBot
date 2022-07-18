# collection of subfunctions like markup keyboard constructors, time converters and others

from telebot import types

# release Data Management:
from database import Deadline
import database


from datetime import datetime
import pytz


def confirmation_text(dl: Deadline):
    """String to be sent in a message before confirmation of a new deadline"""
    text = f'Подтверждаете добавление:\nПредмет: {dl.subject}\nЗадание: {dl.task}\nСрок: {convert_date(dl.date)}?'
    return text


def properties_keyboard():
    """Return keyboard containing buttons to choose property of a Deadline to edit """
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    time_button = types.KeyboardButton('Время')
    name_button = types.KeyboardButton('Предмет')
    task_button = types.KeyboardButton('Задание')
    cancel_button = types.KeyboardButton('Отмена')
    markup.row(name_button, task_button)
    markup.row(time_button, cancel_button)
    return markup


def y_n_keyboard():
    """Return keyboard containing buttons "Yes" and "No" """
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    yes_button = types.KeyboardButton('Да')
    no_button = types.KeyboardButton('Нет')
    markup.row(yes_button, no_button)
    return markup


def y_n_edit_keyboard():
    """Return keyboard containing buttons "Yes", "Edit", "No" """
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    yes_button = types.KeyboardButton('Да')
    edit_button = types.KeyboardButton('Редактировать')
    no_button = types.KeyboardButton('Нет')
    markup.row(yes_button, no_button)
    markup.row(edit_button)
    return markup


def current_time():
    """Returns UTC +3 datetime object"""
    return datetime.now(pytz.timezone('Europe/Moscow')).replace(tzinfo=None)


def convert_date(date: float):
    """Converts timestamp to normal russian date format"""
    return datetime.fromtimestamp(date).strftime('%d.%m %H:%M')


def delta_days(dl: Deadline):
    """Returns days left before deadline"""
    return (datetime.fromtimestamp(dl.date) - current_time()).days


def command_keyboard():
    """ Puts all often used command in keyboard after bot completes a task (e.g., after adding a deadline)"""
    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    add_btn = types.KeyboardButton('/➕Добавить')
    mark_btn = types.KeyboardButton('/✅Отметить')
    show_btn = types.KeyboardButton('/📋Список')
    delete_btn = types.KeyboardButton('/❌Удалить')
    keyboard.row(show_btn, mark_btn)
    keyboard.row(add_btn, delete_btn)
    return keyboard


def deadline_from_input(input_text: str, deadlines: list[Deadline]):
    """Get the deadline object by user import (on delete and edit)"""
    try:
        split = input_text.split(' ', 1)
        dl_id = int(split[0])
        return Deadline.find(dl_id, deadlines)
    except ValueError:
        print("Value error at deadline_from_input!")
        return None
