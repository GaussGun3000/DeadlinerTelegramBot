# main.py
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters, JobQueue
)
from telegram.error import Forbidden, BadRequest

import config
from config import GROUP_CHAT_ID
from messages import MESSAGES as messages
import my_collections
from my_collections import (
    command_keyboard, delta_days, y_n_keyboard, y_n_edit_keyboard,
    confirmation_text, convert_date, all_dl_keyboard, current_time
)
from database import Deadline
import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("deadliner.ptb")

# ===== Load state (same as legacy) =====
deadlines, subscribers = database.load()   # (list[Deadline], dict[user_id] -> list[Deadline])
nonloc_max_id = Deadline.get_max_id(deadlines)
deadline_names = [f'{dln.id} {dln.subject} | {dln.task}' for dln in deadlines]
last_added: dict[int, Deadline] = {}
config.VERIFIED_USERS = database.list_verified()

# ===== Conversation states =====
SUBJECT, TASK, DATE, CONFIRM, EDIT = range(5)
DEL_PICK, DEL_LAST = range(5, 7)
MARK_PICK = 7
EDIT_PICK = 8
ANNOUNCE_TEXT = 9
NOTIFY_INPUT = 10

# ===== Permissions =====
def _is_owner(uid: int) -> bool:
    return config.OWNER_ID and uid == config.OWNER_ID

def _is_admin(uid: int) -> bool:
    # keep your previous admins list behavior
    return uid in getattr(config, "ADMINS", [])

def _is_verified(uid: int) -> bool:
    # Owner always verified; then DB-backed; then legacy static list as fallback
    if _is_owner(uid):
        return True
    if database.is_verified_db(uid):
        return True
    return uid in getattr(config, "VERIFIED_USERS", [])

# ===== Helpers =====
async def _send(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_markup=None):
    await ctx.bot.send_message(chat_id, text, reply_markup=reply_markup)

def create_all_text(show_ids: bool, uid: int):
    text = f'Сейчас {my_collections.current_time().strftime("%d.%m %H:%M")}\n{messages["deadlines"]}\n'
    for dl in deadlines:
        if show_ids:
            text += f' -- {dl.id}  {dl.subject} - {dl.task}\nдо [{convert_date(dl.date)}]'
        else:
            text += f' -- {dl.subject} - {dl.task}\nдо [{convert_date(dl.date)}]'
            if subscribers.get(uid) and dl in subscribers.get(uid):
                text += '\u2705\n'
            else:
                if delta_days(dl) < 1:
                    text += '\u274C\n' if delta_days(dl) < 0 else '\u26A0\n'
                else:
                    text += '\n'
    return text

# ===== Commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(context, update.effective_chat.id, messages['start'] + messages['commands'],
                reply_markup=command_keyboard())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(context, update.effective_chat.id, messages['commands'] + messages['help'],
                reply_markup=command_keyboard())

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await _send(context, update.effective_chat.id,
                f'Your Id: {uid}\nYour username: {update.effective_user.username}',
                reply_markup=command_keyboard())

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_admin(update.effective_chat.id):
        await _send(context, update.effective_chat.id, messages['admin_help'])
    else:
        await _send(context, update.effective_chat.id, messages['on_text'], reply_markup=command_keyboard())

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if len(deadlines) == 0:
        await _send(context, uid, messages['nothing_left'], reply_markup=command_keyboard())
    else:
        await _send(context, uid, create_all_text(False, uid), reply_markup=command_keyboard())

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if _is_verified(uid) and uid not in subscribers.keys():
        database.save_sub(uid, None, 0)
        subscribers[uid] = []
        await rebuild_user_jobs(context.application.job_queue, uid)
        await _send(context, uid, messages['subscribed'], reply_markup=command_keyboard())
    elif uid in subscribers.keys():
        await _send(context, uid, messages['already_subbed'], reply_markup=command_keyboard())
    else:
        await _send(context, uid, messages['not_verified'], reply_markup=command_keyboard())

async def unsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if _is_verified(uid) and uid in subscribers.keys():
        database.save_sub(uid, None, 1)
        subscribers.pop(uid, None)
        for dl in deadlines:
            await unschedule_user_deadline_jobs(context.application.job_queue, uid, dl.id)
        await _send(context, uid, messages['unsubscribed'], reply_markup=command_keyboard())
    elif uid not in subscribers.keys():
        await _send(context, uid, messages['already_unsubbed'], reply_markup=command_keyboard())
    else:
        await _send(context, uid, messages['not_verified'], reply_markup=command_keyboard())

# ===== /add conversation =====
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if not _is_verified(uid):
        await _send(context, uid, messages['not_verified'])
        return ConversationHandler.END
    await _send(context, uid, messages['input_subj'])
    context.user_data['new_dl'] = Deadline(id=nonloc_max_id+1)
    return SUBJECT

async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    if isinstance(text, str):
        dl: Deadline = context.user_data['new_dl']
        dl.subject = text
        await _send(context, update.effective_chat.id, messages['input_task'])
        return TASK
    await _send(context, update.effective_chat.id, f'{messages["wrong_input"]}\n\n{messages["input_subj"]}')
    return SUBJECT

async def get_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    if isinstance(text, str):
        dl: Deadline = context.user_data['new_dl']
        dl.task = text
        await _send(context, update.effective_chat.id, messages['input_date'])
        return DATE
    await _send(context, update.effective_chat.id, f'{messages["wrong_input"]}\n\n{messages["input_task"]}')
    return TASK

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    dl: Deadline = context.user_data['new_dl']
    if isinstance(text, str):
        try:
            now = current_time()
            text_with_year = f'{text} {now.year}'
            date_stamp = datetime.strptime(text_with_year, '%d.%m %H:%M %Y').timestamp()
            if date_stamp > now.timestamp():
                dl.date = date_stamp
                await _send(context, update.effective_chat.id, confirmation_text(dl), reply_markup=y_n_edit_keyboard())
                return CONFIRM
            else:
                await _send(context, update.effective_chat.id, f'{messages["wrong_date"]}\n\n{messages["input_date"]}')
                return DATE
        except ValueError:
            await _send(context, update.effective_chat.id, f'{messages["wrong_format"]}\n\n{messages["input_date"]}')
            return DATE
    await _send(context, update.effective_chat.id, f'{messages["wrong_input"]}\n\n{messages["input_date"]}')
    return DATE

async def confirm_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global nonloc_max_id
    dl: Deadline = context.user_data['new_dl']
    text = update.effective_message.text
    try:
        if text == 'Да':
            nonloc_max_id += 1
            dl.id = nonloc_max_id
            deadlines.append(dl)
            database.save_deadline(dl, 0)
            deadlines.sort()
            await _send(context, update.effective_chat.id, messages['successful_add'], reply_markup=command_keyboard())
            last_added[update.effective_chat.id] = dl
            deadline_names.append(f'{dl.id} {dl.subject} | {dl.task}')
            for uid in list(subscribers.keys()):
                await schedule_user_deadline_jobs(context.application.job_queue, uid, dl, True)
            return ConversationHandler.END
        elif text == 'Нет':
            await _send(context, update.effective_chat.id, messages['deleted'], reply_markup=command_keyboard())
            return ConversationHandler.END
        elif text == 'Редактировать':
            await _send(context, update.effective_chat.id, messages['choose_property'],
                        reply_markup=my_collections.properties_keyboard())
            return EDIT
        else:
            await _send(context, update.effective_chat.id, f'{messages["oops"]}\n\n{confirmation_text(dl)}')
            return CONFIRM
    except TypeError:
        await _send(context, update.effective_chat.id, f'{messages["wrong_input"]}\n\n{confirmation_text(dl)}')
        return CONFIRM

async def edit_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dl: Deadline = context.user_data['new_dl']
    text = update.effective_message.text
    try:
        if text == 'Время':
            await _send(context, update.effective_chat.id, messages['input_date'])
            return DATE
        elif text == 'Предмет':
            await _send(context, update.effective_chat.id, messages['input_subj'])
            return SUBJECT
        elif text == 'Задание':
            await _send(context, update.effective_chat.id, messages['input_task'])
            return TASK
        elif text == 'Отмена':
            await _send(context, update.effective_chat.id, confirmation_text(dl), reply_markup=y_n_edit_keyboard())
            return CONFIRM
        else:
            await _send(context, update.effective_chat.id, messages['oops'], reply_markup=command_keyboard())
            return ConversationHandler.END
    except TypeError:
        await _send(context, update.effective_chat.id, messages['wrong_input'], reply_markup=command_keyboard())
        return ConversationHandler.END

# ===== /delete conversation =====
async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if _is_admin(uid):
        if len(deadlines):
            await show_all(update, context)
            await _send(context, uid, messages['choose_task'], reply_markup=all_dl_keyboard(deadlines))
            return DEL_PICK
        else:
            await _send(context, uid, messages['no_deadlines'], reply_markup=command_keyboard())
            return ConversationHandler.END
    elif _is_verified(uid):
        if last_added.get(uid):
            await _send(context, uid, messages['delete_last'] + f' ({last_added[uid].subject} | {last_added[uid].task})',
                        reply_markup=y_n_keyboard())
            return DEL_LAST
        else:
            await _send(context, uid, messages['no_recent_add'], reply_markup=command_keyboard())
            return ConversationHandler.END
    else:
        await _send(context, uid, messages['not_verified'], reply_markup=command_keyboard())
        return ConversationHandler.END

async def delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    text = update.effective_message.text
    try:
        if text == 'Да':
            database.save_deadline(last_added[uid], 1)
            deadlines.remove(last_added[uid])
            last_added.pop(uid, None)
            await _send(context, uid, messages['deleted'], reply_markup=command_keyboard())
        elif text == 'Нет':
            await _send(context, uid, messages['cancel'], reply_markup=command_keyboard())
        else:
            await _send(context, uid, messages['oops'], reply_markup=command_keyboard())
    except TypeError:
        await _send(context, uid, messages['wrong_input'], reply_markup=command_keyboard())
    return ConversationHandler.END

async def delete_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    try:
        text = update.effective_message.text
        if text in deadline_names:
            dl = my_collections.deadline_from_input(text, deadlines)
            deadlines.remove(dl)
            deadline_names.remove(text)
            database.save_deadline(dl, 1)
            await _send(context, uid, messages['deleted'], reply_markup=command_keyboard())
        elif text == 'Отмена':
            await _send(context, uid, messages['cancel'], reply_markup=command_keyboard())
        else:
            await _send(context, uid, messages['oops'], reply_markup=command_keyboard())
    except TypeError:
        await _send(context, uid, messages['wrong_input'], reply_markup=command_keyboard())
    return ConversationHandler.END

# ===== /mark_done conversation =====
async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if uid in subscribers.keys():
        await _send(context, uid, messages['choose_mark'], reply_markup=all_dl_keyboard(deadlines))
        return MARK_PICK
    else:
        await _send(context, uid, messages['not_subbed'], reply_markup=command_keyboard())
        return ConversationHandler.END

async def choose_to_mark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    try:
        text = update.effective_message.text
        if text in deadline_names:
            chosen_dl = my_collections.deadline_from_input(text, deadlines)
            if chosen_dl in subscribers[uid]:
                subscribers[uid].remove(chosen_dl)
                await _send(context, uid, f'{messages["unmarked"]} "{text}"', reply_markup=command_keyboard())
            else:
                subscribers[uid].append(chosen_dl)
                await _send(context, uid, f'{text} {messages["marked"]}', reply_markup=command_keyboard())
            database.save_sub(uid, subscribers[uid], 2)
        elif text == 'Отмена':
            await _send(context, uid, messages['cancel'], reply_markup=command_keyboard())
    except TypeError:
        await _send(context, uid, messages['wrong_input'], reply_markup=command_keyboard())
    return ConversationHandler.END

# ===== /edit conversation =====
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_admin(update.effective_chat.id):
        await _send(context, update.effective_chat.id, messages['choose_edit'], reply_markup=all_dl_keyboard(deadlines))
        return EDIT_PICK
    else:
        await _send(context, update.effective_chat.id, messages['on_text'], reply_markup=command_keyboard())
        return ConversationHandler.END

async def choose_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    try:
        if text in deadline_names:
            dl = my_collections.deadline_from_input(text, deadlines)
            context.user_data['edit_dl'] = dl
            await _send(context, update.effective_chat.id, messages['input_date'])
            return DATE
        elif text == 'Отмена':
            await _send(context, update.effective_chat.id, messages['cancel'], reply_markup=command_keyboard())
            return ConversationHandler.END
        else:
            await _send(context, update.effective_chat.id, messages['oops'], reply_markup=command_keyboard())
            return ConversationHandler.END
    except TypeError:
        await _send(context, update.effective_chat.id, messages['wrong_input'], reply_markup=command_keyboard())
        return ConversationHandler.END

async def get_date_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    dl: Deadline = context.user_data['edit_dl']
    if isinstance(text, str):
        try:
            now = current_time()
            text_with_year = f'{text} {now.year}'
            date_stamp = datetime.strptime(text_with_year, '%d.%m %H:%M %Y').timestamp()
            if date_stamp >now.timestamp():
                dl.date = date_stamp
                deadlines.sort()
                await _send(context, update.effective_chat.id, messages['date_edited'], reply_markup=command_keyboard())
                database.save_deadline(dl, 2)
                for uid in list(subscribers.keys()): # reschedule jobs
                    await unschedule_user_deadline_jobs(context.application.job_queue, uid, dl.id)
                    await schedule_user_deadline_jobs(context.application.job_queue, uid, dl)
                await send_notification(context, dl, update=True)
                return ConversationHandler.END
            else:
                await _send(context, update.effective_chat.id, f'{messages["wrong_date"]}\n\n{messages["input_date"]}')
                return DATE
        except ValueError:
            await _send(context, update.effective_chat.id, f'{messages["wrong_format"]}\n\n{messages["input_date"]}')
            return DATE
    await _send(context, update.effective_chat.id, f'{messages["wrong_input"]}\n\n{messages["input_date"]}')
    return DATE

# ===== /announce conversation (admins) =====
async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_admin(update.effective_chat.id):
        await _send(context, update.effective_chat.id, messages['announce'])
        return ANNOUNCE_TEXT
    else:
        await _send(context, update.effective_chat.id, messages['on_text'], reply_markup=command_keyboard())
        return ConversationHandler.END

async def get_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    if isinstance(text, str):
        if len(text) < 4000:
            await message_all(context, f'[ОБЪЯВЛЕНИЕ]\n{text}', update.effective_chat.id)
            await context.bot.send_message(
                chat_id=config.GROUP_CHAT_ID,
                message_thread_id=config.ANNOUNCE_TOPIC,
                text=f'[ОБЪЯВЛЕНИЕ]\n{text}'
            )
            await _send(context, update.effective_chat.id, 'Объявление отправлено!', reply_markup=command_keyboard())
        else:
            await _send(context, update.effective_chat.id, messages['len_limit'], reply_markup=command_keyboard())
    else:
        await _send(context, update.effective_chat.id, messages['wrong_input'], reply_markup=command_keyboard())
    return ConversationHandler.END

async def message_all(context: ContextTypes.DEFAULT_TYPE, text: str, sender: int):
    for uid in list(subscribers.keys()):
        try:
            if uid != sender:
                await context.bot.send_message(uid, text)
                await asyncio.sleep(0.05)
        except Forbidden:
            database.save_sub(uid, None, 1)
            subscribers.pop(uid, None)
            log.info(f"Cleaned a subscriber who blocked the bot ({uid})")
        except BadRequest as ex:
            log.warning(f"BadRequest on announcement to {uid}: {ex}")

async def verify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if not _is_owner(uid):
        await _send(context, uid, messages['owner_only'], reply_markup=command_keyboard())
        return

    args = context.args or []
    if len(args) != 1:
        await _send(context, uid, messages['verify_badargs'], reply_markup=command_keyboard())
        return
    try:
        target = int(args[0])
    except ValueError:
        await _send(context, uid, messages['verify_badargs'], reply_markup=command_keyboard())
        return

    database.set_verified(target, True)
    await _send(context, uid, messages['verify_ok'].format(id=target), reply_markup=command_keyboard())

async def unverify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if not _is_owner(uid):
        await _send(context, uid, messages['owner_only'], reply_markup=command_keyboard())
        return

    args = context.args or []
    if len(args) != 1:
        await _send(context, uid, messages['verify_badargs'], reply_markup=command_keyboard())
        return
    try:
        target = int(args[0])
    except ValueError:
        await _send(context, uid, messages['verify_badargs'], reply_markup=command_keyboard())
        return

    database.set_verified(target, False)
    await _send(context, uid, messages['unverify_ok'].format(id=target), reply_markup=command_keyboard())

# ===== /notification-settings =====
async def notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    # Only subbed users can configure (same policy as other user-facing features)
    if not uid in list(subscribers.keys()):
        await _send(context, uid, messages['not_subbed'], reply_markup=command_keyboard())
        return ConversationHandler.END

    await _send(context, uid, messages['notify_intro'], reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton('Отмена')]],
        resize_keyboard=True,
        one_time_keyboard=True,
    ))
    return NOTIFY_INPUT

def _parse_offsets(text: str) -> list[int] | None:
    try:
        parts = [p.strip() for p in text.replace(';', ',').split(',')]
        vals = []
        for p in parts:
            if not p:
                continue
            if not p.lstrip('-').isdigit():
                return None
            vals.append(int(p))
        # validate
        vals = sorted({v for v in vals if 1 <= v <= 1000})
        return vals if vals else None
    except Exception:
        return None

async def save_notification_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    text = update.effective_message.text or ""

    if text.strip().lower() == 'отмена':
        await _send(context, uid, messages['cancel'], reply_markup=command_keyboard())
        return ConversationHandler.END

    offsets = _parse_offsets(text)
    if not offsets:
        await _send(context, uid, messages['notify_bad'], reply_markup=command_keyboard())
        return ConversationHandler.END

    # Try to set for existing subscriber doc; if none, create a stub and set again
    updated = database.set_user_offsets(uid, offsets)
    if not updated:
        database.save_sub(uid, [], 0)               # creates a doc with default profile (no in-memory subscribe)
        database.set_user_offsets(uid, offsets)     # set desired profile

    # If user is actively subscribed in-memory, rebuild their jobs now
    if uid in subscribers:
        await rebuild_user_jobs(context.application.job_queue, uid)

    await _send(context, uid, messages['notify_saved'].format(list=", ".join(map(str, offsets))),
                reply_markup=command_keyboard())
    return ConversationHandler.END

# ===== PTB JobQueue scheduler (replacement for the thread loop) =====
async def clear_past(context: ContextTypes.DEFAULT_TYPE):
    """Clear all expired deadlines from DATABASE (not deadlines list)"""
    now_ts = my_collections.current_time().timestamp()
    for dl in deadlines:
        if now_ts > dl.date:
            database.save_deadline(dl, 1)
            database.clear_marked(dl.id)
            dl.is_past = True

async def send_notification(context: ContextTypes.DEFAULT_TYPE, dl: Deadline, update: bool = False):
    """Sending notification about a deadline (async, PTB-native)."""
    if update:
        text = f'Дата дедлайна "{dl.task}" ({dl.subject})\nизменена на [{convert_date(dl.date)}]!'
    else:
        text = (f'Дедлайн "{dl.task}" предмета "{dl.subject}"\nистекает [{convert_date(dl.date)}].\n'
                f'За работу, зачёт сам себя не получит!')

    for uid in list(subscribers.keys()):
        try:
            md = subscribers.get(uid)  # list or None
            if (md and dl not in md) or not md:
                await context.bot.send_message(uid, text)
                await asyncio.sleep(0.03)
        except Forbidden:
            database.save_sub(uid, None, 1)
            subscribers.pop(uid, None)
            log.info(f"Cleaned a subscriber who blocked the bot. ({uid})")
        except BadRequest as ex:
            log.warning(f"BadRequest on notify {uid}: {ex}")

def _job_name(dl_id: int, user_id: int, off_h: int) -> str:
    return f"remind:{dl_id}:{user_id}:{off_h}"

async def remind_cb(context):
    data = context.job.data or {}
    dl_id = data.get("dl_id")
    user_id = data.get("user_id")
    off = int(data.get("off", -1))
    if dl_id is None or user_id is None:
        return

    # find the deadline in memory
    try:
        dl = Deadline.find(int(dl_id), deadlines)
    except Exception as e:
        print(f"Unknown exception on deadline notification: {e}")
        return

    # skip if deadline is past or user marked it done meanwhile
    if dl.date <= current_time().timestamp():
        return
    md = subscribers.get(user_id)
    if md and dl in md:
        return

    text = (f'Дедлайн "{dl.task}" предмета "{dl.subject}"\n'
            f'истекает [{convert_date(dl.date)}].\n'
            f'За работу, зачёт сам себя не получит!')
    try:
        await context.bot.send_message(user_id, text)
        if off in (72, 24):
            await context.bot.send_message(
                chat_id=config.GROUP_CHAT_ID,
                message_thread_id=config.DEADLINES_TOPIC,
                text=text
            )
    except Forbidden:
        database.save_sub(user_id, None, 1)
        subscribers.pop(user_id, None)
    except BadRequest as ex:
        # log and continue
        print(f"BadRequest on remind {user_id}: {ex}")

async def schedule_user_deadline_jobs(job_queue, user_id: int, dl: Deadline, catch_up: bool = False):
    """Create all reminder jobs for (user, deadline); optionally send a one-time catch-up for nearest missed offset."""
    from datetime import timezone, timedelta, datetime  # if not already imported above

    now = current_time()
    now_ts = now.timestamp()
    if dl.date <= now_ts:
        return

    # skip if user has it marked done
    md = subscribers.get(user_id)
    if md and dl in md:
        return

    offsets = sorted(set(database.get_user_offsets(user_id)))  # ascending & unique
    due_at_utc = datetime.fromtimestamp(dl.date)

    # ---------- catch-up only for newly created deadlines ----------
    if catch_up:
        past_offsets = [int(off) for off in offsets if (due_at_utc - timedelta(hours=int(off))) <= now]
        if past_offsets:
            nearest_past = min(past_offsets)  # closest to "now" (e.g., pick 72 over 144)
            name = _job_name(dl.id, user_id, nearest_past)
            for j in job_queue.get_jobs_by_name(name):
                j.schedule_removal()
            # fire ASAP; use the same callback for consistency
            job_queue.run_once(
                remind_cb,
                when=1,  # ~immediate
                name=name,
                data={"dl_id": dl.id, "user_id": user_id, "off": int(nearest_past)},
            )
            print(f"new catchup notification job to be fired RN ({user_id})")

    # ---------- regular future offsets ----------
    for off in offsets:
        run_at = due_at_utc - timedelta(hours=int(off) + 3)
        if run_at <= now:
            continue
        name = _job_name(dl.id, user_id, int(off))
        for j in job_queue.get_jobs_by_name(name):
            j.schedule_removal()
        job_queue.run_once(
            remind_cb,
            when=run_at,
            name=name,
            data={"dl_id": dl.id, "user_id": user_id, "off": int(off)},
        )
        print(f"new notification job to be fired at {run_at}  ({user_id})")

async def unschedule_user_deadline_jobs(job_queue, user_id: int, dl_id: int):
    """Remove all reminder jobs for a (user, deadline)."""
    for j in list(job_queue.jobs()):
        if isinstance(j.name, str) and j.name.startswith(f"remind:{dl_id}:{user_id}:"):
            j.schedule_removal()

async def rebuild_user_jobs(job_queue, user_id: int):
    """Rebuild all jobs for a given user for all future deadlines."""
    # wipe all reminder jobs for the user
    for j in list(job_queue.jobs()):
        if isinstance(j.name, str) and j.name.startswith("remind:") and f":{user_id}:" in j.name:
            j.schedule_removal()

    now_ts = current_time().timestamp()
    for dl in deadlines:
        if not getattr(dl, "is_past", False) and dl.date > now_ts:
            await schedule_user_deadline_jobs(job_queue, user_id, dl)

async def rebuild_all_jobs(job_queue):
    """Wipe and rebuild all reminder jobs for all subscribers."""
    for j in list(job_queue.jobs()):
        if isinstance(j.name, str) and j.name.startswith("remind:"):
            j.schedule_removal()
    for uid in list(subscribers.keys()):
        await rebuild_user_jobs(job_queue, uid)


# ===== App bootstrap =====
async def _post_init(app):
    app.job_queue.run_repeating(clear_past, interval=config.PERIOD, first=5)  # keep your cleanup
    await rebuild_all_jobs(app.job_queue)


def build_application():
    app = (ApplicationBuilder()
           .token(config.TOKEN)
           .job_queue(JobQueue())
           .post_init(_post_init)
           .concurrent_updates(True)
           .build())

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("show_all", show_all))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsub", unsub))
    app.add_handler(CommandHandler("get_my_id", get_my_id))
    app.add_handler(CommandHandler("admin_help", admin_help))
    app.add_handler(CommandHandler("verify", verify_cmd))
    app.add_handler(CommandHandler("unverify", unverify_cmd))

    # Emoji-button “commands” (buttons send text like "/📋Список", "/➕Добавить", etc.)
    app.add_handler(MessageHandler(filters.Regex(r"^/📋Список$"), show_all))

    # /add conversation
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_entry),
            MessageHandler(filters.Regex(r"^/➕Добавить$"), add_entry),
        ],
        states={
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            TASK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_task)],
            DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_dl)],
            EDIT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_new)],
        },
        fallbacks=[],
    )
    app.add_handler(add_conv)

    # /delete conversation
    del_conv = ConversationHandler(
        entry_points=[
            CommandHandler("delete", delete_cmd),
            MessageHandler(filters.Regex(r"^/❌Удалить$"), delete_cmd),
        ],
        states={
            DEL_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_admin)],
            DEL_LAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_last)],
        },
        fallbacks=[],
    )
    app.add_handler(del_conv)

    # /mark_done conversation
    mark_conv = ConversationHandler(
        entry_points=[
            CommandHandler("mark_done", mark_done),
            MessageHandler(filters.Regex(r"^/✅Отметить$"), mark_done),
        ],
        states={
            MARK_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_to_mark)],
        },
        fallbacks=[],
    )
    app.add_handler(mark_conv)

    # /edit conversation
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit", edit)],
        states={
            EDIT_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_edit)],
            DATE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date_edit)],
        },
        fallbacks=[],
    )
    app.add_handler(edit_conv)

    # /announce conversation
    announce_conv = ConversationHandler(
        entry_points=[CommandHandler("announce", announce)],
        states={
            ANNOUNCE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_announcement)]
        },
        fallbacks=[],
    )
    app.add_handler(announce_conv)

    notify_conv = ConversationHandler(
        entry_points=[CommandHandler("notifications", notification_settings)],
        states={
            NOTIFY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_notification_profile)],
        },
        fallbacks=[],
    )
    app.add_handler(notify_conv)

    # Fallback for any other text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: _send(c, u.effective_chat.id, messages['on_text'], reply_markup=command_keyboard())))

    return app

if __name__ == "__main__":
    application = build_application()
    # run_polling starts the event loop, JobQueue, and blocks
    application.run_polling()

