import discord

from typing import Coroutine, Callable, cast

from secondtry.context import RosterMessageInfo
from secondtry import datastore
import secondtry.context as ctx
from secondtry.cronjobs import WeeklyCronJob, Day

import functools

import logging

log = logging.getLogger(__name__)

ROLE_NAME = "Second Try"
AVAILABLE_EMOJI = "✅"
MAYBE_EMOJI = "❔"
UNAVAILABLE_EMOJI = "❌"
DEFAULT_EMOJI = "➖"


async def find_members_with_role_by_name(guild: discord.Guild, role_name: str):
    """Find all members with a given role name."""
    # Grab the role with the given name
    assert guild is not None
    role = discord.utils.get(guild.roles, name=role_name)

    assert role is not None
    return role.members


TCallback = Callable[[discord.Interaction], Coroutine]


async def send_reminder(member: discord.Member):
    """Send a reminder to a member."""

    # Generate a set of callbacks for the buttons
    async def on_accept(member: discord.Member, interaction: discord.Interaction):
        """Set the member's status to available."""
        await datastore.update_member_status(member.guild, member, AVAILABLE_EMOJI)
        await interaction.response.send_message(
            "Thank you. You have marked yourself as available."
        )

    async def on_maybe(member: discord.Member, interaction: discord.Interaction):
        """Set the member's status to maybe."""
        await datastore.update_member_status(member.guild, member, MAYBE_EMOJI)
        await interaction.response.send_message(
            "Thank you. You have marked yourself as maybe."
        )

    async def on_reject(member: discord.Member, interaction: discord.Interaction):
        """Set the member's status to unavailable."""
        await datastore.update_member_status(member.guild, member, UNAVAILABLE_EMOJI)
        await interaction.response.send_message(
            "Thank you. You have marked yourself as unavailable."
        )

    # Bind the current member to create partials
    on_accept_member = functools.partial(on_accept, member)
    on_maybe_member = functools.partial(on_maybe, member)
    on_reject_member = functools.partial(on_reject, member)

    # Create the view
    view = RosterButtons(
        on_accept_member,
        on_maybe_member,
        on_reject_member,
        timeout=60 * 60 * 24,
    )

    await member.send(
        "Hey! You haven't set your status for this week's raid. Please register your status here: ",
        view=view,
    )

async def send_reminders(guild: discord.Guild):
    """Send the reminder, returns who was reminded."""
    assert guild is not None

    # Get current statuses
    member_statuses = await datastore.get_member_statues(guild)

    # Filter only those with default status
    member_ids = [
        member_id
        for member_id, status in member_statuses.items()
        if status == DEFAULT_EMOJI
    ]

    reminded_names: list[discord.Member] = []

    # Send those members a reminder
    for member_id in member_ids:
        member = guild.get_member(int(member_id))

        if member is None:
            log.warning(
                f"Member {member_id} not found in guild {guild.id} when sending reminder."
            )
            continue

        # Add the name
        reminded_names.append(member.display_name or "Anonymous")

        await send_reminder(member)

    return reminded_names

async def create_reminder_cronjob(
    guild: discord.Guild, day: Day, hour: int, minute: int
):
    """Create a cronjob to send reminders."""
    assert guild is not None
    task = functools.partial(send_reminders, guild)
    return WeeklyCronJob(day, hour, minute, task)


class RosterButtons(discord.ui.View):
    """Buttons for the roster message."""

    def __init__(self, on_accept: TCallback, on_maybe: TCallback, on_reject: TCallback, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.on_accept = on_accept
        self.on_maybe = on_maybe
        self.on_reject = on_reject

    @discord.ui.button(
        label="Available",
        style=discord.ButtonStyle.green,
        custom_id="rosterButtons_accept",
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set the member's status to available."""
        await self.on_accept(interaction)

    @discord.ui.button(
        label="Maybe",
        style=discord.ButtonStyle.blurple,
        custom_id="rosterButtons_maybe",
    )
    async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set the member's status to maybe."""
        await self.on_maybe(interaction)

    @discord.ui.button(
        label="Unavailable",
        style=discord.ButtonStyle.red,
        custom_id="rosterButtons_reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set the member's status to unavailable."""
        await self.on_reject(interaction)


class Roster:
    def __init__(self):
        super().__init__()
        self.message: discord.Message | None = None
        self._guild: discord.Guild | None = None
        self.view = RosterButtons(
            self.on_accept,
            self.on_maybe,
            self.on_reject,
        )
        self.member_statuses = {}

    async def set_guild(self, guild: discord.Guild):
        """Set the guild for this roster."""
        self._guild = guild
        self.member_statuses = await datastore.get_member_statues(guild)
        await self.register_status_observer()

        if self.message is not None:
            await self.update_roster_message()

    async def update_member_status(
        self,
        member: discord.Member,
        status: str | None,
        push: bool = True,
        update: bool = True,
    ):
        """Update the member's status."""
        assert self._guild is not None

        # If the status is None, remove the member from the dictionary
        if status is None:
            if member.id in self.member_statuses:
                del self.member_statuses[member.id]
            return

        if push:
            await datastore.update_member_status(self._guild, member, status)
        else:
            self.member_statuses[str(member.id)] = status
            if update:
                await self.update_roster_message()

    async def update_all_member_statuses(self, statuses: dict[str, str]):
        """Update all member statuses."""
        self.member_statuses = statuses
        await self.update_roster_message()

    async def register_status_observer(self):
        """Register this roster as an observer for the guild."""
        assert self._guild is not None

        # Create a partial function that will call the update_member_status,
        # but not push the changes to the database.
        # This is used when we load the roster from the database.

        await datastore.register_status_observer(
            self._guild, self.update_all_member_statuses
        )

    async def create_status_list(self):
        """Create a list of members with their statuses."""
        assert self._guild is not None
        role = await datastore.get_static_role(self._guild)
        
        assert role is not None

        # Add any members that are not in the database
        for member in role.members:
            if str(member.id) not in self.member_statuses:
                await datastore.update_member_status(
                    self._guild, member, DEFAULT_EMOJI, quiet=True
                )
                self.member_statuses[str(member.id)] = DEFAULT_EMOJI

        names = "\n".join(
            f"- {member.display_name}: {self.member_statuses[str(member.id)] }"
            for member in role.members
        )

        return names

    async def create_embed(self):
        """Create the embed for the roster message."""
        embed = discord.Embed(
            title="Signups",
            description=f"Signups for the static",
            color=discord.Color.green(),
        ).add_field(
            name="Members",
            value=await self.create_status_list(),
            inline=False,
        )
        return embed

    async def on_accept(self, interaction: discord.Interaction):
        """Set the member's status to available."""
        await self.update_member_status(
            cast(discord.Member, interaction.user), AVAILABLE_EMOJI
        )
        await interaction.response.send_message(
            "You have marked yourself as available.", ephemeral=True, delete_after=5
        )

    async def on_maybe(self, interaction: discord.Interaction):
        """Set the member's status to maybe."""
        await self.update_member_status(
            cast(discord.Member, interaction.user), MAYBE_EMOJI
        )
        await interaction.response.send_message(
            "You have marked yourself as maybe.", ephemeral=True, delete_after=5
        )

    async def on_reject(self, interaction: discord.Interaction):
        """Set the member's status to unavailable."""
        await self.update_member_status(
            cast(discord.Member, interaction.user), UNAVAILABLE_EMOJI
        )
        await interaction.response.send_message(
            "You have marked yourself as unavailable.", ephemeral=True, delete_after=5
        )

    async def update_roster_message(self):
        """Update the roster message with the new embed."""
        assert self.message is not None
        embed = await self.create_embed()
        log.info(f"Updating roster message: {self.message.id}")
        await self.message.edit(embed=embed, view=self.view, content=None)

    @classmethod
    async def from_roster_info(cls, roster_info: RosterMessageInfo):
        """Create a roster from the roster info."""
        roster = cls()
        guild = ctx.client.get_guild(roster_info["guild_id"])

        if guild is None:
            raise ValueError(f"Guild {roster_info['guild_id']} not found")

        await roster.set_guild(guild)

        channel = guild.get_channel(roster_info["channel_id"])

        assert isinstance(channel, discord.TextChannel)
        roster.message = await channel.fetch_message(roster_info["id"])

        await roster.update_roster_message()

        return roster

    @classmethod
    async def inject(cls, message: discord.Message):
        """Inject the roster into the message."""
        roster = cls()
        roster.message = message

        assert message.guild is not None
        await roster.set_guild(message.guild)

        return roster
