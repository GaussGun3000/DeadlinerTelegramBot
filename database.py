from typing import Union

import psycopg2
import os

from dataclasses import dataclass, field


@dataclass
class Deadline:
    id: int = 0
    subject: str = None
    task: str = None
    date: float = 0  # date as a timestamp
    is_past: bool = False  # whether a deadline has passed.
    notified: int = 0  # whether subs were notified about a deadline. 7 - week before, 3 - 3 days before, 1 - a day before

    def __lt__(self, other):
        return self.date < other.date  # defines list sorting (by date)

    @staticmethod
    def find(dl_id: int, dl_list: list):
        res = [dl for dl in dl_list if dl.id == dl_id]
        if len(res):
            return res[0]
        else:
            raise(IndexError("Deadlines.find(): no deadline with this ID"))


def deadline_by_name(name: str, deadlines: list[Deadline]):  # find a Deadline object by subject and task
    subj, task = name.split(' | ')
    for dl in deadlines:
        if dl.subject == subj and dl.task == task:
            return dl
    return None


def __connect():
    """defines which database to connect (debug or release)"""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    if dir_path == "C:\\Users\\vva07\\OneDrive\\Документы\\проекты\\Deadliner0307":  # debug
        import pwd
        return psycopg2.connect(host="localhost", port="5432", user="postgres", password=pwd.password, database="Deadliner0307")
    else:  # release
        DATABASE_URL = os.environ['DATABASE_URL']
        return psycopg2.connect(DATABASE_URL, sslmode='require')


def save_deadline(dl: Deadline, add: int):
    """
     :param add: Defines action: 0 - add new row, 1 - remove row, 2 - update row

     Saving a Deadline example to database.
     """
    with __connect() as db:
        subject = dl.subject
        task = dl.task
        date = dl.date
        notified = dl.notified
        try:
            cursor = db.cursor()
            if add == 0:
                query = """INSERT INTO deadlines (subject, task, date, notified) VALUES (%s,%s,%s,%s,%s)"""
                cursor.execute(query, (subject, task, date, notified))
            elif add == 1:
                query = """DELETE from deadlines where subject=%s AND task=%s"""
                cursor.execute(query, (subject, task))
            else:
                query = """UPDATE deadlines set notified=%s, date=%s where subject=%s AND task=%s"""
                cursor.execute(query, (notified, date, subject, task))
            cursor.close()
            db.commit()
        except psycopg2.Error as er:
            print('DATABASE ON SAVE DL EXCEPTION:\n', er)


def save_sub(user_id: int, marked_done: Union[list, None], add: int):
    """
    :param add: Defines action: 0 - add new row, 1 - remove row, 2 - update row

    Saving a subscriber and his tasks marked as done to database.
    """
    with __connect() as db:
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


def clear_marked(dl_id: int):
    with __connect() as db:
        try:
            cursor = db.cursor()
            query = """UPDATE subscribers set marked_done = array_remove(marked_done, %s) WHERE %s = any(marked_done)"""
            cursor.execute(query, (dl_id, dl_id))
            cursor.close()
            db.commit()
        except psycopg2.Error as er:
            print('DATABASE ON SAVE SUB EXCEPTION:\n', er)


def load():
    with __connect() as db:
        try:
            cursor = db.cursor()
            query = """SELECT dl_id, subject, task, date, notified FROM deadlines ORDER BY date"""
            cursor.execute(query)
            deadlines = list()
            for data in cursor:
                deadlines.append(Deadline(id=data[0], subject=data[1], task=data[2], date=data[3],
                                          notified=data[4]))
            query = """SELECT user_id, marked_done FROM subscribers"""
            cursor.execute(query)
            subscribers = dict()
            for data in cursor:
                if data[1]:
                    subscribers[int(data[0])] = [Deadline.find(x, deadlines) for x in data[1]]
                else:
                    subscribers[data[0]] = list()
            return deadlines, subscribers
        except psycopg2.Error as er:
            print('DATABASE ON LOAD EXCEPTION:\n', er)
