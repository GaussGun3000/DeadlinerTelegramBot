# database.py
from typing import Union, Tuple, Dict, List
import os
from dataclasses import dataclass

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

# ---- Your original dataclass stays the same (imported by main.py) ----
from dataclasses import dataclass

@dataclass
class Deadline:
    id: int = 0
    subject: str = None
    task: str = None
    date: float = 0.0      # timestamp (seconds)
    is_past: bool = False  # used only in-memory

    def __lt__(self, other):
        return self.date < other.date

    @staticmethod
    def find(dl_id: int, dl_list: list):
        res = [dl for dl in dl_list if dl.id == dl_id]
        if len(res):
            return res[0]
        else:
            raise(IndexError("Deadlines.find(): no deadline with this ID"))

    @staticmethod
    def get_max_id(dl_list: list):
        max_id = 0
        for dl in dl_list:
            if max_id < dl.id:
                max_id = dl.id
        return max_id

DEFAULT_NOTIFY_OFFSETS = [24]
# ===================== Mongo bootstrap =====================

_MONGO_CLIENT: MongoClient | None = None
_DB_NAME = os.getenv("DB_NAME", "deadliner")
_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

def _db():
    global _MONGO_CLIENT
    if _MONGO_CLIENT is None:
        _MONGO_CLIENT = MongoClient(_MONGO_URI)
        db = _MONGO_CLIENT[_DB_NAME]
        try:
            # deadlines: helpful for sorting by upcoming
            db["deadlines"].create_index([("date", ASCENDING)])
            # subscribers: DO NOT create an index on _id — it already exists & is unique
            # db["subscribers"].create_index([("_id", ASCENDING)], unique=True)  # <-- remove this
        except Exception as er:
            print("DATABASE INDEX SETUP WARNING:", er)
    return _MONGO_CLIENT[_DB_NAME]


def _deadlines():
    return _db()["deadlines"]

def _subs():
    return _db()["subscribers"]


# ===================== Parity API =====================

def save_deadline(dl: Deadline, add: int):
    """
    :param add: 0 add new row, 1 remove row, 2 update row
    Behavior mirrors the original Postgres version.
    - On add, we insert with _id = dl.id (caller sets id, as in current app).
    - On delete/update, we match by (subject, task) just like the original.
    """
    try:
        col = _deadlines()
        if add == 0:
            # insert new deadline; use the app-generated id
            doc = {
                "_id": dl.id,
                "subject": dl.subject,
                "task": dl.task,
                "date": float(dl.date),
            }
            col.insert_one(doc)
        elif add == 1:
            # delete by subject+task (keeps parity with your old code)
            col.delete_one({"subject": dl.subject, "task": dl.task})
        else:
            # update notified/date by subject+task
            col.update_one(
                {"subject": dl.subject, "task": dl.task},
                {"$set": {"date": float(dl.date)}}
            )
    except PyMongoError as er:
        print('DATABASE ON SAVE DL EXCEPTION:\n', er)


def save_sub(user_id: int, marked_done: Union[list[Deadline], None], add: int):
    """
    :param add: 0 add new row, 1 remove row, 2 update row
    Exactly like the original: add/remove subscriber; update marked_done.
    """
    try:
        col = _subs()
        if add == 0:
            # create with empty or provided marked_done
            dl_ids = [dl.id for dl in marked_done] if marked_done else []
            col.update_one({"_id": int(user_id)},
                           {"$setOnInsert": {"marked_done": dl_ids,
                                             "notify_offsets_h": DEFAULT_NOTIFY_OFFSETS[:] }}, upsert=True)
        elif add == 1:
            col.delete_one({"_id": int(user_id)})
        else:
            # update full list
            dl_ids = [dl.id for dl in marked_done] if marked_done else []
            col.update_one({"_id": int(user_id)}, {"$set": {"marked_done": dl_ids}})
    except PyMongoError as er:
        print('DATABASE ON SAVE SUB EXCEPTION:\n', er)


def clear_marked(dl_id: int):
    """Remove a deadline id from every subscriber's marked_done array."""
    try:
        _subs().update_many({}, {"$pull": {"marked_done": int(dl_id)}})
    except PyMongoError as er:
        print('DATABASE ON CLEAR MARKED EXCEPTION:\n', er)


def load() -> tuple[list[Deadline], dict[int, list[Deadline]]]:
    """
    Load all deadlines sorted by date, and subscribers with marked_done list.
    This mirrors your original load() behavior.
    Returns: (deadlines_list, subscribers_dict)
    """
    try:
        # deadlines
        dls: list[Deadline] = []
        for doc in _deadlines().find({}, sort=[("date", ASCENDING)]):
            dls.append(Deadline(
                id=int(doc["_id"]),
                subject=doc["subject"],
                task=doc["task"],
                date=float(doc["date"]),
            ))

        # subscribers
        subs: dict[int, list[Deadline]] = {}
        for doc in _subs().find({}):
            uid = int(doc["_id"])
            ids = doc.get("marked_done") or []
            # Map marked_done ids back to Deadline objects (parity with Postgres version)
            try:
                subs[uid] = [Deadline.find(x, dls) for x in ids]
            except IndexError:
                # If a referenced deadline is missing, skip it gracefully
                subs[uid] = [Deadline.find(x, dls) for x in ids if any(d.id == x for d in dls)]

        return dls, subs
    except PyMongoError as er:
        print('DATABASE ON LOAD EXCEPTION:\n', er)
        return [], {}

def _verified():
    return _db()["verified_users"]

def set_verified(user_id: int, verified: bool) -> None:
    try:
        if verified:
            _verified().update_one({"_id": int(user_id)}, {"$setOnInsert": {}}, upsert=True)
        else:
            _verified().delete_one({"_id": int(user_id)})
    except PyMongoError as er:
        print("DATABASE ON SET VERIFIED EXCEPTION:\n", er)

def is_verified_db(user_id: int) -> bool:
    try:
        return _verified().find_one({"_id": int(user_id)}) is not None
    except PyMongoError as er:
        print("DATABASE ON IS VERIFIED EXCEPTION:\n", er)
        return False

def list_verified() -> list[int]:
    try:
        return [int(d["_id"]) for d in _verified().find({}, projection={"_id": 1})]
    except PyMongoError as er:
        print("DATABASE ON LIST VERIFIED EXCEPTION:\n", er)
        return []

def get_user_offsets(user_id: int) -> list[int]:
    try:
        doc = _subs().find_one({"_id": int(user_id)}, projection={"notify_offsets_h": 1})
        if doc and isinstance(doc.get("notify_offsets_h"), list):
            return [int(x) for x in doc["notify_offsets_h"] if isinstance(x, (int, float))]
        return DEFAULT_NOTIFY_OFFSETS[:]
    except PyMongoError as er:
        print("DATABASE ON GET USER OFFSETS EXCEPTION:\n", er)
        return DEFAULT_NOTIFY_OFFSETS[:]

def set_user_offsets(user_id: int, offsets_h: list[int]) -> bool:
    """Returns True if user exists (is subscribed) and we updated; False otherwise."""
    try:
        res = _subs().update_one(
            {"_id": int(user_id)},
            {"$set": {"notify_offsets_h": [int(x) for x in offsets_h]}}
        )
        return res.matched_count > 0
    except PyMongoError as er:
        print("DATABASE ON SET USER OFFSETS EXCEPTION:\n", er)
        return False
