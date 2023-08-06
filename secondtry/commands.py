from secondtry import datastore

import discord
import secondtry.context as ctx
from secondtry.roster import (
    AVAILABLE_EMOJI,
    UNAVAILABLE_EMOJI,
    MAYBE_EMOJI,
    DEFAULT_EMOJI,
    Roster,
    send_reminder,
    send_reminders
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
    
    # Ensure we have a static role set
    assert interaction.guild is not None
    static_role = await datastore.get_static_role(interaction.guild)

    if static_role is None:
        await interaction.response.send_message(
            "You must set a static role first.", ephemeral=True
        )
        return

    # Check if an existing roster message exists
    # If it does, we delete it
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
@ctx.is_admin
async def reset(interaction: discord.Interaction):
    """Reset all statuses to default."""
    assert interaction.guild is not None
    await datastore.reset_members(interaction.guild)
    await interaction.response.send_message(
        "All statuses reset.", ephemeral=True, delete_after=5
    )


@ctx.command(name="remind", description="Send a reminder to all members who haven't responded yet.")
@ctx.is_admin
async def remind_all(interaction: discord.Interaction):
    """Send a reminder to all users from the guild."""
    assert interaction.guild is not None

    # This can take a bit, so we declare the response as deferred
    await interaction.response.defer(ephemeral=True)

    reminded = await send_reminders(interaction.guild)
    await interaction.response.send_message(
        f"Reminder sent to: {[x.mention for x in reminded]}", ephemeral=True
    )

@ctx.command(name="staticrole", description="Send the role required to be a static member.")
@ctx.is_admin
async def static_role(interaction: discord.Interaction, role: discord.Role):
    """Send the role required to be a static member."""
    assert interaction.guild is not None
    await datastore.set_static_role(interaction.guild, role)

    # Update the roster
    await datastore.force_update(interaction.guild)

    await interaction.response.send_message(
        f"Static role set to: {role.mention}", ephemeral=True, delete_after=5
    )


@ctx.command(name="adminrole", description="Send the role required to run admin commands.")
@ctx.is_admin
async def admin_role(interaction: discord.Interaction, role: discord.Role):
    """Send the role required to run admin commands."""
    assert interaction.guild is not None
    await datastore.set_admin_role(interaction.guild, role)
    await interaction.response.send_message(
        f"Admin role set to: {role.mention}", ephemeral=True, delete_after=5
    )



@ctx.command(name="testreminder", description="Test reminder.")
@ctx.is_admin
async def test_reminder(interaction: discord.Interaction, member: discord.Member):
    """Test reminder."""
    assert interaction.guild is not None
    assert isinstance(interaction.user, discord.Member)
    await send_reminder(member)
    await interaction.response.send_message(
        "Test sent.", ephemeral=True, delete_after=5
    )