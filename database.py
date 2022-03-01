import psycopg2
import os
import config
from dataclasses import dataclass, field


@dataclass
class Deadline:
    subject: str = None
    task: str = None
    date: float = 0  # date as a timestamp
    reminder_days: int = 0  # days before expiry to start reminding
    is_past: bool = False  # whether a deadline has passed.
    notified: int = 0  # whether subs were notified about a deadline. 7 - week before, 3 - 3 days before, 1 - a day before

    def __lt__(self, other):
        return self.date < other.date


def deadline_by_name(name: str, deadlines: list):  # find a Deadline object by subject and task
    subj, task = name.split(' | ')
    for dl in deadlines:
        if dl.subject == subj and dl.task == task:
            return dl
    return None


DATABASE_URL = os.environ['DATABASE_URL']


def save_deadline(dl: Deadline, add: int):
    """ Saving a Deadline example to database.
    Add param: 0 - add, 1 - remove, 2 - update """
    with psycopg2.connect(DATABASE_URL, sslmode='require') as db:
        subject = dl.subject
        task = dl.task
        date = dl.date
        reminder_days = dl.reminder_days
        notified = dl.notified
        try:
            cursor = db.cursor()
            if add == 0:
                query = """INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES (%s,%s,%s,%s,%s)"""
                cursor.execute(query, (subject, task, date, reminder_days, notified))
            elif add == 1:
                query = """DELETE from deadlines where subject=%s AND task=%s"""
                cursor.execute(query, (subject, task))
            else:
                query = """UPDATE deadlines set notified=%s, reminder_days=%s, date=%s where subject=%s AND task=%s"""
                cursor.execute(query, (notified, reminder_days, date, subject, task))
            cursor.close()
            db.commit()
        except psycopg2.Error as er:
            print('DATABASE ON SAVE DL EXCEPTION:\n', er)


def save_sub(user_id: int, marked_done: list, add: int):
    """ Saving a subscriber and his tasks marked as done to database.
    Add param: 0 - add, 1 - remove, 2 - update """
    with psycopg2.connect(DATABASE_URL, sslmode='require') as db:
        try:
            cursor = db.cursor()
            if add == 0:
                query = """INSERT INTO subscribers (user_id) VALUES (%s)"""
                cursor.execute(query, (user_id,))
            elif add == 1:
                query = """DELETE from subscribers where user_id=%s"""
                cursor.execute(query, (user_id, ))
            else:
                query = """UPDATE subscribers set marked_done=%s where user_id=%s"""
                cursor.execute(query, ('_'.join(marked_done), user_id))
            cursor.close()
            db.commit()
        except psycopg2.Error as er:
            print('DATABASE ON SAVE SUB EXCEPTION:\n', er)


def load():
    with psycopg2.connect(DATABASE_URL, sslmode='require') as db:
        try:
            cursor = db.cursor()
            query = """SELECT subject, task, date, reminder_days, notified FROM deadlines ORDER BY date"""
            cursor.execute(query)
            deadlines = list()
            for data in cursor:
                deadlines.append(Deadline(subject=data[0], task=data[1], date=data[2], reminder_days=data[3], notified=data[4]))
            query = """SELECT user_id, marked_done FROM subscribers"""
            cursor.execute(query)
            subscribers = dict()
            for data in cursor:
                if data[1]:
                    subscribers[data[0]] = data[1].split('_')
                    for marked_done in subscribers[data[0]]:  # cleaning deleted deadlines from marked_tasks for each subscriber
                        if not deadline_by_name(marked_done, deadlines):
                            subscribers[data[0]].remove(marked_done)
                    save_sub(data[0], subscribers[data[0]], 2)
                else:
                    subscribers[data[0]] = list()
            return deadlines, subscribers
        except psycopg2.Error as er:
            print('DATABASE ON LOAD EXCEPTION:\n', er)
