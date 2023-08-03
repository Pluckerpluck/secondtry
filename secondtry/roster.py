import discord

from typing import Coroutine, Callable, cast

from secondtry.context import RosterMessageInfo
from secondtry import datastore
import secondtry.context as ctx

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


class RosterButtons(discord.ui.View):
    """Buttons for the roster message."""

    def __init__(self, on_accept: TCallback, on_maybe: TCallback, on_reject: TCallback):
        super().__init__(timeout=None)
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
        self, member: discord.Member, status: str | None, push: bool = True, update: bool = True
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
        static_members = await find_members_with_role_by_name(self._guild, ROLE_NAME)

        # Add any members that are not in the database
        for member in static_members:
            if str(member.id) not in self.member_statuses:
                await datastore.update_member_status(self._guild, member, DEFAULT_EMOJI, quiet=True)
                self.member_statuses[str(member.id)] = DEFAULT_EMOJI

        names = "\n".join(
            f"- {member.display_name}: {self.member_statuses[str(member.id)] }"
            for member in static_members
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


# self.member_statuses[interaction.user.id] = "✅"
# self.member_statuses[interaction.user.id] = "❔"
# self.member_statuses[interaction.user.id] = "❌"


# class RosterButtons(discord.ui.View):
#     """Buttons for the roster message."""
#     def __init__(self):
#         super().__init__(timeout=None)


#     @discord.ui.button(label="Available", style=discord.ButtonStyle.green, custom_id="rosterButtons_accept")
#     async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Set the member's status to available."""
#         assert interaction.guild is not None
#         handler = _HANDLERS.get(interaction.guild.id)

#         if handler is None:
#             return await interaction.response.send_message("No roster registered for this guild!", ephemeral=True)

#         await handler.on_accept(interaction)

#     @discord.ui.button(label="Maybe", style=discord.ButtonStyle.blurple, custom_id="rosterButtons_maybe")
#     async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Set the member's status to maybe."""
#         assert interaction.guild is not None
#         handler = _HANDLERS.get(interaction.guild.id)

#         if handler is None:
#             return await interaction.response.send_message("No roster registered for this guild!", ephemeral=True)

#         await handler.on_maybe(interaction)


#     @discord.ui.button(label="Unavailable", style=discord.ButtonStyle.red, custom_id="rosterButtons_reject")
#     async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Set the member's status to unavailable."""
#         assert interaction.guild is not None
#         handler = _HANDLERS.get(interaction.guild.id)

#         if handler is None:
#             return await interaction.response.send_message("No roster registered for this guild!", ephemeral=True)

#         await handler.on_reject(interaction)
