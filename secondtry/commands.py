from secondtry import datastore

import discord
import secondtry.context as ctx
from secondtry.roster import (
    AVAILABLE_EMOJI,
    UNAVAILABLE_EMOJI,
    MAYBE_EMOJI,
    DEFAULT_EMOJI,
    Roster,
)


@ctx.command(
    name="roster",
    description="Print the signup roster for the static into the desired channel.",
)
async def print_roster(interaction: discord.Interaction, channel: discord.TextChannel):
    """Print the roster for the static into the provided channel."""

    # Ensure we're in a valid channel type
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "You must run this command in a text channel.", ephemeral=True
        )
        return

    # Check if an existing roster message exists
    # If it does, we delete it
    assert interaction.guild is not None
    roster_message_id = await datastore.get_roster_message_id(interaction.guild)
    was_deleted = False
    if roster_message_id is not None:
        prev_channel = ctx.client.get_channel(roster_message_id["channel_id"])
        assert isinstance(prev_channel, discord.TextChannel)
        message = await prev_channel.fetch_message(roster_message_id["id"])
        await message.delete()
        was_deleted = True

    # Create the roster message
    message = await channel.send("Roster loading...")

    # Inject the roster into the previous message
    await Roster.inject(message)

    # Save the roster message id so we can reconnect to it after a restart
    await datastore.save_roster_message_id(interaction.guild, message)

    # Let the user know we posted the roster
    # (We have to respond with something)
    msg = (
        "Roster Posted, replacing existing message."
        if was_deleted
        else "Roster Posted."
    )
    await interaction.response.send_message(msg, ephemeral=True)


@ctx.command(name="available", description="Mark yourself as available for the static.")
async def available(interaction: discord.Interaction):
    """Mark the user as available for the static."""
    assert interaction.guild is not None
    assert isinstance(interaction.user, discord.Member)
    await datastore.update_member_status(
        interaction.guild, interaction.user, AVAILABLE_EMOJI
    )
    await interaction.response.send_message(
        "You have marked yourself as available.", ephemeral=True, delete_after=5
    )


@ctx.command(
    name="maybe", description="Mark yourself as maybe available for the static."
)
async def maybe(interaction: discord.Interaction):
    """Mark the user as maybe available for the static."""
    assert interaction.guild is not None
    assert isinstance(interaction.user, discord.Member)
    await datastore.update_member_status(
        interaction.guild, interaction.user, MAYBE_EMOJI
    )
    await interaction.response.send_message(
        "You have marked yourself as maybe.", ephemeral=True, delete_after=5
    )


@ctx.command(
    name="unavailable", description="Mark yourself as unavailable for the static."
)
async def unavailable(interaction: discord.Interaction):
    """Mark the user as unavailable for the static."""
    assert interaction.guild is not None
    assert isinstance(interaction.user, discord.Member)
    await datastore.update_member_status(
        interaction.guild, interaction.user, UNAVAILABLE_EMOJI
    )
    await interaction.response.send_message(
        "You have marked yourself as unavailable.", ephemeral=True, delete_after=5
    )


@ctx.command(name="reset", description="Reset all statuses to default.")
async def reset(interaction: discord.Interaction):
    """Reset all statuses to default."""
    assert interaction.guild is not None
    await datastore.reset_members(interaction.guild)
    await interaction.response.send_message(
        "All statuses reset.", ephemeral=True, delete_after=5
    )
