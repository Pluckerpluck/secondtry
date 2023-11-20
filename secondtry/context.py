"""Context.

Centralized context for the bot.
"""
import asyncio
import typing
import discord
import functools
import os

import logging

from secondtry import datastore

log = logging.getLogger(__name__)


class RosterMessageInfo(typing.TypedDict):
    guild_id: int
    channel_id: int
    id: int


# Initialize the bot
_intents = discord.Intents.default()
_intents.members = True

client = discord.Client(intents=_intents)
tree = discord.app_commands.CommandTree(client)


_events = {}


def event(func):
    """Register event.

    We use this instead of the client.event decorator because we need to
    register multiple event handlers for the same event.
    """
    log.info(
        f"Registering event {func.__name__} [{func.__code__.co_filename}:{func.__code__.co_firstlineno}]]"
    )

    # If the event is not in the dict, add it
    if func.__name__ not in _events:
        _events[func.__name__] = []

        # Register an event handler for the event
        @client.event
        @functools.wraps(func)
        async def _event_handler(*args, **kwargs):
            """Event handler."""
            log.info(f"Running event handler for {func.__name__}")

            # Call each of the event handlers asynchronously
            await asyncio.gather(
                *[event(*args, **kwargs) for event in _events[func.__name__]]
            )

    # Add the event to the dict
    _events[func.__name__].append(func)

    return func


def is_bot_owner(func):
    """Check if the user is the bot owner."""

    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        """Wrapper."""
        if interaction.user.id != int(os.environ["BOT_OWNER"]):
            return await interaction.response.send_message(
                "You are not the bot owner.", ephemeral=True, delete_after=5
            )

        return await func(interaction, *args, **kwargs)

    return wrapper


def is_admin(func):
    """Check if the user is an admin (or bot owner)."""

    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        """Wrapper."""
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used in a guild."
            )

        admin_role = await datastore.get_admin_role(interaction.guild)
        
        member = interaction.user
        assert isinstance(member, discord.Member)

        if member.id != int(os.environ["BOT_OWNER"]) and admin_role not in member.roles:
            return await interaction.response.send_message(
                "You are not an admin.", ephemeral=True, delete_after=5
            )

        return await func(interaction, *args, **kwargs)

    return wrapper


@event
async def on_ready():
    print(f"We have logged in as {client.user}")


command = tree.command


def new_group(name: str, description: str):
    """Create a new command group."""
    group = discord.app_commands.Group(name=name, description=description)
    tree.add_command(group)
    return group


def run():
    """Run the bot."""
    client.run(
        os.environ["DISCORD_TOKEN"],
    )
