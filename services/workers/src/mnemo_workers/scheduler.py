"""APScheduler-based periodic trigger.

Dramatiq itself has no cron primitive; we run APScheduler in a separate
process (one replica) that enqueues actors. Compose can scale this with
`docker compose up --scale scheduler=1`.
"""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from mnemo_workers.tasks.digest import run_daily_digest_for_all_users


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    # 09:00 UTC daily — users can configure per-user delivery time in v2.
    scheduler.add_job(
        lambda: run_daily_digest_for_all_users.send(),
        CronTrigger(hour=9, minute=0),
        id="daily_digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=600,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
