import asyncio
import logging

from secondtry.cronjobs import start_cron_jobs, add_weekly_job, WeeklyCronJob

logging.basicConfig(level=logging.INFO)

import aioconsole
import discord

# Import the commands
# This is necessary to register them
import secondtry.commands
import secondtry.context as ctx
from secondtry.roster import Roster
from secondtry import datastore
import os

async def load_roster_message(guild: discord.Guild) -> bool:
    roster_info = await datastore.get_roster_message_id(guild)

    # If there is no roster message, we skip this guild
    if roster_info is None:
        return False

    roster = await Roster.from_roster_info(roster_info)

    # We need to add the view to the client so it can process the interactions
    ctx.client.add_view(roster.view)

    return True

async def schedule_reminder_cronjob(guild: discord.Guild):
    reminder_timer = await datastore.get_reminder_time(guild)

    if reminder_timer is None:
        return
    
    # Schedule the cronjob
    await add_weekly_job(reminder_timer.day, reminder_timer.hour, reminder_timer.minute, None)

@ctx.event
async def on_ready():
    """When the bot is ready, start the CLI and hook up the roster views."""
    if os.environ.get("CLI") == "1":
        asyncio.create_task(cli())

    asyncio.create_task(start_cron_jobs())

    for guild in ctx.client.guilds:
        # First we load any active roster messages
        existing_roster = await load_roster_message(guild)

        # If we have no existing roster, then nothing else matters
        if not existing_roster:
            continue

        # Then we load any reminders

async def cli():
    """Command line interface.
    
    Used to sync the command tree with Discord,
    and to exit the program.
    """
    while command := await aioconsole.ainput("Commands: "):
        if command == "sync":
            await sync()
        elif command == "exit":
            exit()
        else:
            print("Unknown command")


async def sync():
    """Sync the command tree, updating the commands on Discord."""
    print("Syncing...")
    await ctx.tree.sync()
    print("Synced!")


if __name__ == "__main__":
    ctx.run()
