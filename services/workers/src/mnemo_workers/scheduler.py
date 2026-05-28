"""APScheduler-based periodic trigger.

Dramatiq itself has no cron primitive; we run APScheduler in a separate
process (one replica) that enqueues actors. Compose can scale this with
`docker compose up --scale scheduler=1`.
"""

from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from mnemo_workers.metrics_server import start_metrics_server
from mnemo_workers.tasks.cleanup import run_idempotency_cleanup
from mnemo_workers.tasks.digest import run_daily_digest_for_all_users
from mnemo_workers.tasks.notion_sync import run_notion_sync_for_all_users
from mnemo_workers.tasks.obsidian_export import run_obsidian_export_for_all_users


def main() -> None:
    start_metrics_server()
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

    # Every 15 min — push ready notes to user-configured Notion DBs.
    scheduler.add_job(
        lambda: run_notion_sync_for_all_users.send(),
        IntervalTrigger(minutes=15),
        id="notion_sync",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Every 30 min — write ready notes as .md files into each user's vault.
    scheduler.add_job(
        lambda: run_obsidian_export_for_all_users.send(),
        IntervalTrigger(minutes=30),
        id="obsidian_export",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Hourly — drop idempotency-key rows older than 24h.
    scheduler.add_job(
        lambda: run_idempotency_cleanup.send(),
        IntervalTrigger(hours=1),
        id="idempotency_cleanup",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    scheduler.start()


if __name__ == "__main__":
    main()
