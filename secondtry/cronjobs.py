import asyncio
from datetime import datetime, timedelta
import enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

import discord

import logging

log = logging.getLogger(__name__)

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
    def __init__(self, task: Callable[..., Coroutine], args: tuple = ()):
        self.last_run: datetime | None = None
        self.task = task
        self.args = args

    def should_run(self):
        """Check if the task should run."""
        raise NotImplementedError

    async def run(self):
        """Run the task."""
        # We set the last run time first, to prevent the task from running twice

        # TODO: Save the last run time in the datastore
        # This will allow us to restart the bot without re-running the task

        self.last_run = datetime.now()
        log.info(f"Running task {self.task.__name__}, args: {self.args}")
        await self.task(*self.args)


class DailyCronJob(CronJob):
    """Class to represent a cron job."""

    def __init__(self, hour: int, minute: int, task: Callable[..., Coroutine], args: tuple = ()):
        super().__init__(task, args)
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
        return datetime.now() >= scheduled_time


class WeeklyCronJob(CronJob):
    """Class to represent a cron job."""

    def __init__(self, day: Day, hour: int, minute: int, task: Callable[..., Coroutine], args: tuple = ()):
        super().__init__(task, args)
        self.day = day
        self.hour = hour
        self.minute = minute

    def should_run(self):
        """Check if the task should run."""
        # If we last ran the task already today, we don't need to run it again
        if self.last_run is not None and self.last_run.date() == datetime.now().date():
            return False
        
        # We're only going to run if it's the right day of the week
        if self.day.value != datetime.now().weekday():
            return False

        # Scheduled time for the week
        scheduled_time = datetime.now().replace(hour=self.hour, minute=self.minute)

        # Otherwise if we're overdue, run the task
        return datetime.now() >= scheduled_time


JOBS: dict[str, CronJob] = {}

def add_daily_job(hour: int, minute: int, task: Callable[..., Coroutine], args: tuple = ()) -> str:
    """Add a daily job."""
    
    # Each task is given a random ID
    id_ = str(uuid4())
    JOBS[id_] = DailyCronJob(hour, minute, task, args)

    return id_

def add_weekly_job(day: Day, hour: int, minute: int, task: Callable[..., Coroutine], args: tuple = ()) -> str:
    """Add a weekly job."""
    
    # Each task is given a random ID
    id_ = str(uuid4())
    JOBS[id_] = WeeklyCronJob(day, hour, minute, task, args)

    return id_

def remove_job(id: str):
    """Remove a job."""
    if id in JOBS:
        del JOBS[id]


async def start_cron_jobs():
    """Start the cron jobs."""
    log.info("Starting cron jobs")
    while True:
        # Check for tasks every 60 seconds
        log.debug("Checking cron jobs")
        await asyncio.sleep(60)

        # Loop all jobs, and run them if they need to run
        for id, job in JOBS.items():
            log.debug(f"Checking cron job {id}")
            if job.should_run():
                log.info(f"Running cron job {id}")
                asyncio.create_task(job.run())
