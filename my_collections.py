# my_collections.py (PTB types)
from typing import List
from xmlrpc.client import DateTime

from telegram import ReplyKeyboardMarkup, KeyboardButton

from database import Deadline
import database

from datetime import datetime
import pytz

def confirmation_text(dl: Deadline):
    return f'Подтверждаете добавление:\nПредмет: {dl.subject}\nЗадание: {dl.task}\nСрок: {convert_date(dl.date)}?'

from telegram import ReplyKeyboardMarkup, KeyboardButton

def properties_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('Предмет'), KeyboardButton('Задание')],
            [KeyboardButton('Время'), KeyboardButton('Отмена')],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def y_n_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('Да'), KeyboardButton('Нет')],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def y_n_edit_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('Да'), KeyboardButton('Нет')],
            [KeyboardButton('Редактировать')],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def command_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('/📋Список'), KeyboardButton('/✅Отметить')],
            [KeyboardButton('/➕Добавить'), KeyboardButton('/❌Удалить')],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def all_dl_keyboard(deadlines: List):
    rows = [[KeyboardButton(f'{dl.id} {dl.subject} | {dl.task}')] for dl in deadlines]
    rows.append([KeyboardButton('Отмена')])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def current_time() -> datetime:
    return datetime.now(pytz.timezone('Europe/Moscow')).replace(tzinfo=None)

def convert_date(date: float):
    return datetime.fromtimestamp(date).strftime('%d.%m %H:%M')

def delta_days(dl: Deadline):
    return (datetime.fromtimestamp(dl.date) - current_time()).days

def deadline_from_input(input_text: str, deadlines: list[Deadline]):
    try:
        split = input_text.split(' ', 1)
        dl_id = int(split[0])
        return Deadline.find(dl_id, deadlines)
    except ValueError:
        print("Value error at deadline_from_input!")
        return None
