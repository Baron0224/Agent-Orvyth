"""Deliver desktop reminders independently of the Orvyth web backend."""
from contextlib import closing
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

from chat_web import configured_desktop_owner, default_database_path
from reminder_delivery import claim


def notify(title, body, tag):
    env = dict(os.environ, ORVYTH_TOAST_TITLE=title, ORVYTH_TOAST_BODY=body, ORVYTH_TOAST_TAG=tag)
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-File",
         str(Path(__file__).with_name("reminder_toast.ps1"))],
        env=env, check=True, timeout=7, creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def deliver(path, owner, now, log):
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10)) as db, db:
        # Keep each claim uncommitted until Windows accepts its notification.
        db.execute("BEGIN IMMEDIATE")
        task_ids = db.execute(
            "SELECT id FROM tasks WHERE owner=? AND remind_time IS NOT NULL ORDER BY created",
            (owner,),
        ).fetchall()
        claimed = [result for (task_id,) in task_ids if (result := claim(db, owner, task_id, now, catch_up=True))]
        if claimed:
            missed = sum(late for _, late in claimed)
            titles = [("已过期：" if late else "") + text for text, late in claimed]
            tag = uuid.uuid4().hex[:16]
            title = f"Orvyth 提醒 · {missed} 条已过期" if missed else "Orvyth 提醒"
            notify(title, "\n".join(titles), tag)
            db.commit()
            log.info("notification accepted by Windows tag=%s items=%s overdue=%s", tag, len(titles), missed)


def main():
    path = default_database_path()
    file_handler = RotatingFileHandler(path.with_name("reminder-worker.log"), maxBytes=262144,
                                      backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[file_handler],
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("orvyth.reminders")
    log.info("worker started")
    while True:
        try:
            owner = configured_desktop_owner()
            if not owner:
                raise ValueError("Missing configured daily account")
            deliver(path, owner, datetime.now().astimezone(), log)
        except (OSError, sqlite3.Error, subprocess.SubprocessError, ValueError) as error:
            log.warning("poll failed, will retry (%s)", type(error).__name__)
        time.sleep(2)


if __name__ == "__main__":
    main()
