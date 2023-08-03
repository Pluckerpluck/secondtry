import asyncio
import logging

logging.basicConfig(level=logging.INFO)

import aioconsole
import discord

# Import the commands
# This is necessary to register them
import secondtry.commands
import secondtry.context as ctx
from secondtry.roster import Roster
from secondtry import datastore


@ctx.event
async def on_ready():
    """When the bot is ready, start the CLI and hook up the roster views."""
    asyncio.create_task(cli())

    for guild in ctx.client.guilds:
        roster_info = await datastore.get_roster_message_id(guild)

        # If there is no roster message, we skip this guild
        if roster_info is None:
            continue

        roster = await Roster.from_roster_info(roster_info)

        # We need to add the view to the client so it can process the interactions
        ctx.client.add_view(roster.view)

        # Ensure the roster message is up to date
        await roster.update_roster_message()


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
