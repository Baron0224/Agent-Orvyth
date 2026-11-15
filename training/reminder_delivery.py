"""Atomically claim one occurrence of an Orvyth reminder."""
from datetime import date, datetime, time, timedelta
import sqlite3


def claim(db, owner, task_id, now, *, catch_up=False, grace=0):
    db.row_factory = sqlite3.Row
    task = db.execute(
        "SELECT * FROM tasks WHERE owner=? AND id=? AND remind_time IS NOT NULL",
        (owner, task_id),
    ).fetchone()
    if task is None or task["done"]:
        return None
    timestamp = now.timestamp()
    if task["due_at"] is not None:
        due = task["due_at"]
        occurrence = None
    else:
        day = now.date()
        clock = time.fromisoformat(task["remind_time"])
        due = datetime.combine(day, clock).timestamp()
        if catch_up:
            if due > timestamp:
                day -= timedelta(days=1)
            if task["end_date"]:
                day = min(day, date.fromisoformat(task["end_date"]))
            due = datetime.combine(day, clock).timestamp()
        occurrence = day.isoformat()
        if occurrence < task["start_date"] or (task["end_date"] and occurrence > task["end_date"]):
            return None
        if task["created"] > due and occurrence != now.date().isoformat():
            return None
    if timestamp < due + grace:
        return None
    missed = int(catch_up and timestamp - due > 8)
    if occurrence is None:
        claimed = db.execute(
            """UPDATE tasks SET fired_at=?, missed=?
               WHERE owner=? AND id=? AND due_at=? AND COALESCE(fired_at,0)=0
               AND last_done_date IS NULL AND done=0 RETURNING title""",
            (timestamp, missed, owner, task_id, due),
        ).fetchone()
    else:
        claimed = db.execute(
            """UPDATE tasks SET fired_at=?, last_fire_date=?, missed=?
               WHERE owner=? AND id=? AND due_at IS NULL AND remind_time=?
               AND (last_fire_date IS NULL OR last_fire_date<?)
               AND (last_done_date IS NULL OR last_done_date<?)
               AND start_date<=? AND (end_date IS NULL OR end_date>=?)
               AND done=0 RETURNING title""",
            (timestamp, occurrence, missed, owner, task_id, task["remind_time"],
             occurrence, occurrence, occurrence, occurrence),
        ).fetchone()
    return (claimed["title"], bool(missed)) if claimed else None
