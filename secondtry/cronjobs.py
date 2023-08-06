import asyncio
from datetime import datetime, timedelta
import enum
from typing import Callable, Coroutine
from uuid import uuid4

class Day(enum.Enum):
    """Enum representing a day of the week."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

class CronJob:
    def __init__(self, task: Callable[[], Coroutine]):
        self.last_run: datetime | None = None
        self.task = task

    def should_run(self):
        """Check if the task should run."""
        raise NotImplementedError

    async def run(self):
        """Run the task."""
        # We set the last run time first, to prevent the task from running twice
        self.last_run = datetime.now()
        await self.task()


class DailyCronJob(CronJob):
    """Class to represent a cron job."""

    def __init__(self, hour: int, minute: int, task: Callable[[], Coroutine]):
        super().__init__(task)
        self.hour = hour
        self.minute = minute

    def should_run(self):
        """Check if the task should run."""
        # If we last ran the task today, we don't need to run it again
        if self.last_run is not None and self.last_run.date() == datetime.now().date():
            return False

        # Scheduled time for the day
        scheduled_time = datetime.now().replace(hour=self.hour, minute=self.minute)

        # Otherwise if we're overdue, run the task
        return datetime.now() > scheduled_time


class WeeklyCronJob(CronJob):
    """Class to represent a cron job."""

    def __init__(self, day: Day, hour: int, minute: int, task: Callable[[], Coroutine]):
        super().__init__(task)
        self.day = day
        self.hour = hour
        self.minute = minute

    def should_run(self):
        """Check if the task should run."""
        # If we last ran the task within a week of today, we don't need to run it again
        if (
            self.last_run is not None
            and self.last_run.date() >= datetime.now().date() - timedelta(days=7)
        ):
            return False
        
        # Scheduled time for the week
        scheduled_time = datetime.now().replace(
            hour=self.hour, minute=self.minute, day=self.day.value
        )

        # Otherwise if we're overdue, run the task
        return datetime.now() > scheduled_time


JOBS = {}

def add_daily_job(hour: int, minute: int, task: Callable[[], Coroutine]) -> str:
    """Add a daily job."""
    
    # Each task is given a random ID
    id_ = str(uuid4())
    JOBS[id_] = DailyCronJob(hour, minute, task)

    return id_

def add_weekly_job(day: Day, hour: int, minute: int, task: Callable[[], Coroutine]) -> str:
    """Add a weekly job."""
    
    # Each task is given a random ID
    id_ = str(uuid4())
    JOBS[id_] = WeeklyCronJob(day, hour, minute, task)

    return id_


async def start_cron_jobs():
    """Start the cron jobs."""
    while True:
        # Check for tasks every 60 seconds
        await asyncio.sleep(60)

        # Loop all jobs, and run them if they need to run
        async with asyncio.TaskGroup() as group:
            for job in JOBS.values():
                if job.should_run():
                    group.create_task(job.run())
