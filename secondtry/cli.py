import asyncio
import logging

from secondtry.cronjobs import start_cron_jobs, add_weekly_job, WeeklyCronJob

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

import aioconsole
import discord

# Import the commands
# This is necessary to register them
import secondtry.commands
import secondtry.context as ctx
from secondtry.roster import Roster, cron_send_reminder
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
        weekly_reminder = await datastore.get_reminder_time(guild)
        if weekly_reminder is not None:

            new_id = add_weekly_job(
                weekly_reminder.day,
                weekly_reminder.hour,
                weekly_reminder.minute,
                cron_send_reminder,
                (guild,)
            )
            log.info(f"Adding weekly reminder for {guild.name}: {new_id}")

            # Save the new ID into our datastore
            await datastore.set_reminder_time(
                guild, new_id, weekly_reminder.day, weekly_reminder.hour, weekly_reminder.minute
            )


        

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
