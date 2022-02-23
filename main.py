import time
from datetime import datetime
from threading import Thread
import my_collections
from my_collections import command_keyboard, delta_days, y_n_keyboard, y_n_edit_keyboard, confirmation_text, \
    convert_date
import telebot
from telebot.apihelper import ApiTelegramException
import config
from telebot import types
# release Data Management:
#from database import Deadline
#import database
# debug DM:
from debug import database
from debug.database import Deadline

"""
TODO LIST:
- early completion reward
- notification profiles
"""


def deadliner0307():
    bot = telebot.TeleBot(config.TOKEN)
    # list of Deadline data objects (check database.py); dict of users subscribed and tasks they marked as done:
    deadlines, subscribers = database.load()

    def deadline_by_name(name: str):
        """find a Deadline object in list of all by "name" - subject and task"""
        subj, task = name.split(' | ')
        for dl in deadlines:
            if dl.subject == subj and dl.task == task:
                return dl

    deadline_names = list()  # <Bad code architecture>
    for dln in deadlines:  # list of "deadline names" to help "delete deadline" code
        deadline_names.append(f'{dln.subject} | {dln.task}')
    for tasks_key, tasks_done in subscribers.items():
        dls = list()
        for dl_str in tasks_done:
            if dl_str in deadline_names:
                dls.append(deadline_by_name(dl_str))
        subscribers[tasks_key] = dls  # </Bad code architecture>

    print(subscribers, deadline_names, sep='\n')
    last_added = dict()  # user <-> his last added. To clear accidentally added deadlines by user themself. Dict resets daily!

    @bot.message_handler(commands='start')
    def start(message):
        bot.send_message(message.chat.id, config.messages['start'] + config.messages['commands'],
                         reply_markup=command_keyboard())

    # noinspection PyTypeChecker
    @bot.message_handler(commands='subscribe')
    def sub(message):  # adding a user to subscribers list on his command if not already
        if message.chat.id in config.VERIFIED_USERS and message.chat.id not in subscribers.keys():
            database.save_sub(message.chat.id, None, 0)
            subscribers[message.chat.id] = list()
            bot.send_message(message.chat.id, config.messages['subscribed'], reply_markup=command_keyboard())
        elif message.chat.id in subscribers.keys():
            bot.send_message(message.chat.id, config.messages['already_subbed'], reply_markup=command_keyboard())
        else:
            bot.send_message(message.chat.id, config.messages['not_verified'], reply_markup=command_keyboard())

    # noinspection PyTypeChecker
    @bot.message_handler(commands='unsub')
    def unsub(message):  # removing a user to subscribers list on his command if not already
        if message.chat.id in config.VERIFIED_USERS and message.chat.id in subscribers.keys():
            database.save_sub(message.chat.id, None, 1)
            subscribers.pop(message.chat.id)
            bot.send_message(message.chat.id, config.messages['unsubscribed'], reply_markup=command_keyboard())
        elif message.chat.id not in subscribers.keys():
            bot.send_message(message.chat.id, config.messages['already_unsubbed'], reply_markup=command_keyboard())
        else:
            bot.send_message(message.chat.id, config.messages['not_verified'], reply_markup=command_keyboard())

    @bot.message_handler(commands=['show_all', '📋Список'])
    def show_all(message, called: bool = False):  # output all deadlines (expired deadlines stored until daily restart)
        if len(deadlines) == 0:
            bot.send_message(message.chat.id, config.messages['nothing_left'], reply_markup=command_keyboard())
        else:
            text = f'Сейчас {my_collections.current_time().strftime("%d.%m %H:%M")}\n' + f'{config.messages["deadlines"]}\n'
            for dl in deadlines:
                text += f' -- \"{dl.subject}\" - \"{dl.task}\"\nдо [{convert_date(dl.date)}]'
                if subscribers.get(message.chat.id) and dl in subscribers.get(
                        message.chat.id):  # if deadline marked as done by user
                    text += '\u2705\n'
                else:
                    if delta_days(dl) < 1:  # if less than a day left put warning sign
                        if delta_days(dl) < 0:
                            text += '\u274C\n'
                        else:
                            text += '\u26A0\n'
                    else:
                        text += '\n'
            if called:
                bot.send_message(message.chat.id, text)
            else:
                bot.send_message(message.chat.id, text, reply_markup=command_keyboard())

    @bot.message_handler(commands=['add', '➕Добавить'])
    def add(message):  # adding a new deadline. Verified users only.
        if message.chat.id in config.VERIFIED_USERS:
            msg = bot.send_message(message.chat.id, config.messages['input_subj'])
            bot.register_next_step_handler(msg, get_subject)
        else:
            bot.send_message(message.chat.id, config.messages['not_verified'])

    def get_subject(message, new_deadline: Deadline = Deadline(), edit_flag: bool = False):
        """Reading user's message, writing into subject of new deadline
        If new_deadline arg is passed, then editing its contents
        (for edit mode edit_flag should be true to proceed straight to confirm message)"""
        text = message.text
        if type(text) == str:
            new_deadline.subject = text
            if edit_flag:
                msg = bot.send_message(message.chat.id, confirmation_text(new_deadline),
                                       reply_markup=y_n_edit_keyboard())
                bot.register_next_step_handler(msg, confirm_dl, new_deadline)
            else:
                msg = bot.send_message(message.chat.id, config.messages['input_task'])
                bot.register_next_step_handler(msg, get_task, new_deadline)
        else:
            msg = bot.send_message(message.chat.id,
                                   f'{config.messages["wrong_input"]}\n\n{config.messages["input_subj"]}')
            bot.register_next_step_handler(msg, get_subject)

    def get_task(message, new_dl: Deadline, edit_flag: bool = False):
        """Getting new task value or editing it for existing deadline object
        (for edit mode edit_flag should be true to proceed straight to confirm message)"""
        text = message.text
        if type(text) == str:
            new_dl.task = text
            if edit_flag:
                msg = bot.send_message(message.chat.id, confirmation_text(new_dl), reply_markup=y_n_edit_keyboard())
                bot.register_next_step_handler(msg, confirm_dl, new_dl)
            else:
                msg = bot.send_message(message.chat.id, config.messages['input_date'])
                bot.register_next_step_handler(msg, get_date, new_dl, False)
        else:
            msg = bot.send_message(message.chat.id,
                                   f'{config.messages["wrong_input"]}\n\n{config.messages["input_task"]}')
            bot.register_next_step_handler(msg, get_task, new_dl)

    def get_date(message, new_dl: Deadline, edit_flag: bool):
        """Getting Deadline date value. Requires user to follow specific format ("dd.mm HH:MM").
         Edit = True doesn't trigger next step (for edit menu)"""
        text = message.text
        if type(text) == str:
            try:  # trying to convert user's input to timestamp. If user's input is wrong, tell them to try again
                text += f' {datetime.now().year}'
                date_stamp = datetime.strptime(text, '%d.%m %H:%M %Y').timestamp()
                if date_stamp > datetime.now().timestamp():  # if user's date is from the past, tell them to try again
                    if edit_flag:
                        old_time = new_dl.date
                        new_dl.date = date_stamp
                        if old_time < date_stamp:
                            new_dl.notified = 0
                        deadlines.sort()
                        bot.send_message(message.chat.id, config.messages['date_edited'],
                                         reply_markup=command_keyboard())
                        database.save_deadline(new_dl, 2)
                        send_notification(new_dl, True)
                    else:
                        new_dl.date = date_stamp
                        msg = bot.send_message(message.chat.id, confirmation_text(new_dl),
                                               reply_markup=y_n_edit_keyboard())
                        bot.register_next_step_handler(msg, confirm_dl, new_dl)
                else:
                    msg = bot.send_message(message.chat.id,
                                           f'{config.messages["wrong_date"]}\n\n{config.messages["input_date"]}')
                    bot.register_next_step_handler(msg, get_date, new_dl, edit_flag)
            except ValueError:
                msg = bot.send_message(message.chat.id,
                                       f'{config.messages["wrong_format"]}\n\n{config.messages["input_date"]}')
                bot.register_next_step_handler(msg, get_date, new_dl, edit_flag)

    def confirm_dl(message, new_dl: Deadline):  # getting confirmation to add a new deadline.
        try:
            if message.text == 'Да':
                new_dl.notified = 0
                deadlines.append(new_dl)
                database.save_deadline(new_dl, 0)
                deadlines.sort()
                bot.send_message(message.chat.id, config.messages['successful_add'], reply_markup=command_keyboard())
                last_added[message.chat.id] = new_dl
                deadline_names.append(f'{new_dl.subject} | {new_dl.task}')
            elif message.text == 'Нет':
                bot.send_message(message.chat.id, config.messages['deleted'], reply_markup=command_keyboard())
            elif message.text == 'Редактировать':
                msg = bot.send_message(message.chat.id, config.messages['choose_property'],
                                       reply_markup=my_collections.properties_keyboard())
                bot.register_next_step_handler(msg, edit_new, new_dl)
            else:
                msg = bot.send_message(message.chat.id,
                                       f'{config.messages["oops"]}\n\n{confirmation_text(new_dl)}')
                bot.register_next_step_handler(msg, confirm_dl, new_dl)
        except TypeError:
            msg = bot.send_message(message.chat.id,
                                   f'{config.messages["wrong_input"]}\n\n{confirmation_text(new_dl)}')
            bot.register_next_step_handler(msg, confirm_dl, new_dl)

    def edit_new(message: types.Message, new_dl: Deadline):
        try:
            if message.text == 'Время':
                msg = bot.send_message(message.chat.id, config.messages['input_date'])
                bot.register_next_step_handler(msg, get_date, new_dl, False)
            elif message.text == 'Предмет':
                msg = bot.send_message(message.chat.id, config.messages['input_subj'])
                bot.register_next_step_handler(msg, get_subject, new_dl, True)
            elif message.text == 'Задание':
                msg = bot.send_message(message.chat.id, config.messages['input_task'])
                bot.register_next_step_handler(msg, get_task, new_dl, True)
            elif message.text == 'Отмена':
                msg = bot.send_message(message.chat.id, confirmation_text(new_dl), reply_markup=y_n_edit_keyboard())
                bot.register_next_step_handler(msg, confirm_dl, new_dl)
            else:
                bot.send_message(message.chat.id, config.messages["oops"], reply_markup=command_keyboard())
        except TypeError:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    @bot.message_handler(commands=['delete', '❌Удалить'])
    def delete(message):  # Deleting deadline last added by a verified user, any by an admin
        if message.chat.id in config.ADMINS:
            if len(deadlines):
                show_all(message)
                msg = bot.send_message(message.chat.id, config.messages['choose_task'], reply_markup=all_dl_keyboard())
                bot.register_next_step_handler(msg, delete_admin)
            else:
                bot.send_message(message.chat.id, config.messages['no_deadlines'], reply_markup=command_keyboard())
        elif message.chat.id in config.VERIFIED_USERS:
            if last_added.get(message.chat.id):
                msg = bot.send_message(message.chat.id, config.messages['delete_last'] +
                                       f' ({last_added[message.chat.id].subject} | {last_added[message.chat.id].task})',
                                       reply_markup=y_n_keyboard())
                bot.register_next_step_handler(msg, delete_last)
            else:
                bot.send_message(message.chat.id, config.messages['no_recent_add'], reply_markup=command_keyboard())
        else:
            bot.send_message(message.chat.id, config.messages['not_verified'], reply_markup=command_keyboard())

    def delete_last(message):  # delete deadline last added by user
        try:
            if message.text == 'Да':
                database.save_deadline(last_added[message.chat.id], 1)
                deadlines.remove(last_added[message.chat.id])
                last_added.pop(message.chat.id)
                deadline_names.remove(message.text)
                bot.send_message(message.chat.id, config.messages['deleted'], reply_markup=command_keyboard())
            elif message.text == 'Нет':
                bot.send_message(message.chat.id, config.messages['cancel'], reply_markup=command_keyboard())
            else:
                bot.send_message(message.chat.id, config.messages["oops"], reply_markup=command_keyboard())
        except TypeError:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    def delete_admin(message):  # delete deadline chosen by admin
        try:
            if message.text in deadline_names:
                dl = deadline_by_name(message.text)
                deadlines.remove(dl)
                deadline_names.remove(message.text)
                database.save_deadline(dl, 1)
                bot.send_message(message.chat.id, config.messages['deleted'], reply_markup=command_keyboard())
            elif message.text == 'Отмена':
                bot.send_message(message.chat.id, config.messages['cancel'], reply_markup=command_keyboard())
            else:
                bot.send_message(message.chat.id, config.messages["oops"], reply_markup=command_keyboard())
        except TypeError:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    @bot.message_handler(commands=['mark_done', '✅Отметить'])
    # user marks a task as done not to receive notifications about it
    def mark_done(message):
        if message.chat.id in subscribers.keys():
            msg = bot.send_message(message.chat.id, config.messages['choose_mark'], reply_markup=all_dl_keyboard())
            bot.register_next_step_handler(msg, choose_to_mark)
        else:
            bot.send_message(message.chat.id, config.messages['not_subbed'], reply_markup=command_keyboard())

    def choose_to_mark(message):
        try:  # a deadline name should be in message.text
            uid = message.chat.id
            text = message.text
            if text in deadline_names:
                chosen_dl = deadline_by_name(text)
                if chosen_dl in subscribers[uid]:
                    subscribers[uid].remove(chosen_dl)
                    bot.send_message(uid, f'{config.messages["unmarked"]} \"{text}\"', reply_markup=command_keyboard())
                else:
                    subscribers[uid].append(chosen_dl)
                    bot.send_message(uid, f'{text} {config.messages["marked"]}', reply_markup=command_keyboard())
                dl_list = list()  # preparing to update marked tasks in database
                for dl in subscribers[uid]:
                    dl_list.append(f'{dl.subject} | {dl.task}')
                # my_collections.send_reward()
                database.save_sub(uid, dl_list, 2)
            elif text == 'Отмена':
                bot.send_message(message.chat.id, config.messages['cancel'], reply_markup=command_keyboard())
        except TypeError:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    @bot.message_handler(commands=['help'])
    def commands(message):
        bot.send_message(message.chat.id, config.messages['commands'] + config.messages['help'],
                         reply_markup=command_keyboard())

    @bot.message_handler(commands=['announce'])
    def announce(message):  # announcement to all subscribed users. Text is inputted by an admin
        if message.chat.id in config.ADMINS:
            msg = bot.send_message(message.chat.id, config.messages['announce'])
            bot.register_next_step_handler(msg, get_announcement)
        else:
            bot.send_message(message.chat.id, config.messages['on_text'], reply_markup=command_keyboard())

    def get_announcement(message: telebot.types.Message):
        """Reads admin's announcement from chat and sends it"""
        text = message.text
        if type(text) == str:
            if len(text) < 4000:
                message_all(f'[ОБЪЯВЛЕНИЕ]\n{text}', message.chat.id)
                bot.send_message(message.chat.id, 'Объявление отправлено!', reply_markup=command_keyboard())
            else:
                bot.send_message(message.chat.id, config.messages["len_limit"], reply_markup=command_keyboard())
        else:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    def message_all(text: str, sender: int):
        """Send a message to all subs with following text, ignoring sender"""
        for uid in subscribers.keys():
            try:
                if uid != sender:
                    bot.send_message(uid, text)
                    time.sleep(0.05)
            except ApiTelegramException as ex:
                if str(ex.result_json['description']) == "Forbidden: bot was blocked by the user":
                    database.save_sub(uid, None, 1)
                    print("Cleaned a subscriber who blocked the bot.")
                else:
                    print(f"EXCEPTION ON SEND ANNOUNCEMENT:\n{ex}")

    @bot.message_handler(commands=['edit'])
    def edit(message):  # edit date of a deadline. Admin function.
        if message.chat.id in config.ADMINS:
            msg = bot.send_message(message.chat.id, config.messages['choose_edit'], reply_markup=all_dl_keyboard())
            bot.register_next_step_handler(msg, choose_edit)
        else:
            bot.send_message(message.chat.id, config.messages['on_text'], reply_markup=command_keyboard())

    def choose_edit(message: types.Message):
        """Determine edited deadline and pass it to get_date with edit_flag=1"""
        try:
            if message.text in deadline_names:
                dl = deadline_by_name(message.text)
                msg = bot.send_message(message.chat.id, config.messages['input_date'])
                bot.register_next_step_handler(msg, get_date, dl, True)
            elif message.text == 'Отмена':
                bot.send_message(message.chat.id, config.messages['cancel'], reply_markup=command_keyboard())
            else:
                bot.send_message(message.chat.id, config.messages["oops"], reply_markup=command_keyboard())
        except TypeError:
            bot.send_message(message.chat.id, config.messages["wrong_input"], reply_markup=command_keyboard())

    @bot.message_handler(commands=['get_my_id'])  # display to a user their id. Needed for manual verification
    def get_user_id(message):
        uid = message.from_user.id
        bot.send_message(message.chat.id, f'Your Id: {uid}\nYour username: {message.from_user.username}',
                         reply_markup=command_keyboard())
        return uid

    @bot.message_handler(commands=['admin_help'])  # show list of admin commands [admin only]
    def admin_help(message):
        if message.chat.id in config.ADMINS:
            bot.send_message(message.chat.id, config.messages['admin_help'], reply_markup=None)
        else:
            bot.send_message(message.chat.id, config.messages['on_text'], reply_markup=command_keyboard())

    @bot.message_handler(content_types=['text'])  # if user sends text when a command expected
    def on_text(message):
        bot.send_message(message.chat.id, config.messages['on_text'], reply_markup=command_keyboard())

    def all_dl_keyboard():
        """ Puts all deadlines in a keyboard as different buttons. Returns the keyboard object """
        keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for dl in deadlines:
            keyboard.add(types.KeyboardButton(f'{dl.subject} | {dl.task}'))
        keyboard.add(types.KeyboardButton('Отмена'))
        return keyboard

    def auto_task():
        """All periodic tasks will be ran here (e.g., notifications) with Threading"""
        while True:
            time.sleep(config.PERIOD)
            clear_past()
            notify_users()

    def clear_past():  # clear all expired deadlines from DATABASE (not deadlines list)
        for dl in deadlines:
            if my_collections.current_time().timestamp() > dl.date:
                database.save_deadline(dl, 1)
                dl.is_past = True

    def notify_users():  # preparing notifications 1, 3, 7 days before deadline if haven't yet
        for dl in deadlines:
            if dl.notified == 0:
                if 3 < delta_days(dl) < 7:
                    dl.notified = 7
                    database.save_deadline(dl, 2)
                    send_notification(dl)
                elif 1 < delta_days(dl) < 3:
                    dl.notified = 3
                    database.save_deadline(dl, 2)
                    send_notification(dl)
                elif delta_days(dl) < 1:
                    dl.notified = 1
                    database.save_deadline(dl, 2)
                    send_notification(dl)
            elif dl.notified == 7:
                if delta_days(dl) < 3:
                    send_notification(dl)
                    dl.notified = 3
                    database.save_deadline(dl, 2)
            elif dl.notified == 3:
                if delta_days(dl) < 1:
                    send_notification(dl)
                    dl.notified = 1
                    database.save_deadline(dl, 2)

    def send_notification(dl: Deadline, update: bool = False):  # sending notification about a deadline
        if update:
            text = f'Дата дедлайна \"{dl.task}\" ({dl.subject})\nизменена на [{convert_date(dl.date)}]!'
        else:
            text = f'Дедлайн \"{dl.task}\" предмета \"{dl.subject}\"\nистекает [{convert_date(dl.date)}].\n' \
                   f'За работу, зачёт сам себя не получит!'
        # don't send notification if user has marked a task as done.
        # subscribers.get(uid) is needed to avoid exceptions on empty list of marked_done tasks
        for uid in subscribers.keys():
            try:
                # "or not subscribers.get(uid, None)" needed to actually notify anyone with empty marked_done list
                if (subscribers.get(uid) and dl not in subscribers.get(uid)) or not subscribers.get(uid, None):
                    bot.send_message(uid, text)
                    time.sleep(0.1)
            except ApiTelegramException as ex:
                if str(ex.result_json['description']) == "Forbidden: bot was blocked by the user":
                    database.save_sub(uid, None, 1)
                    send_notification(dl, update)
                    print("Cleaned a subscriber who blocked the bot.")
                else:
                    print(f"EXCEPTION ON SEND NOTIFICATION:\n{ex}")

    Thread(target=auto_task).start()
    bot.polling(none_stop=True, interval=1)


if __name__ == '__main__':
    deadliner0307()
