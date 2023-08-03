import typing
import discord
import tinydb
from tinydb.table import Document


db = tinydb.TinyDB("data/datastore.json")

from secondtry.context import RosterMessageInfo




# async def get_roster_docs() -> dict[int, RosterMessageInfo]:
#     """Get all roster documents from the datastore."""
#     rosters = {}
#     for guild_doc in db.all():
#         if "roster_message" not in guild_doc:
#             continue

#         roster_message = guild_doc["roster_message"]

#         rosters[guild_doc.doc_id] = {
#             "guild_id": guild_doc.doc_id,
#             "channel_id": roster_message["channel_id"],
#             "id": roster_message["id"],
#         }


#     return rosters


async def get_guild_doc(guild: discord.Guild) -> Document:
    """Get the guild document from the datastore, creating it if it doesn't exist."""
    doc = db.get(doc_id=guild.id)

    if doc is None:
        db.insert(Document({}, doc_id=guild.id))
        return await get_guild_doc(guild)

    assert isinstance(doc, Document)

    return doc


async def save_roster_role(guild: discord.Guild, role: discord.Role):
    """Save the role required to be included in the roster."""
    doc = await get_guild_doc(guild)
    doc["roster_role"] = role.id
    db.update(doc, doc_ids=[guild.id])


async def get_roster_role(guild: discord.Guild) -> discord.Role | None:
    """Get the roster role from the datastore."""
    doc = db.get(doc_id=guild.id)
    if doc is None:
        return None

    assert isinstance(doc, Document)

    role_id = doc.get("roster_role")

    if role_id is None:
        return None

    return guild.get_role(role_id)


async def save_roster_message_id(guild: discord.Guild, message: discord.Message):
    """Save the roster message ID to the datastore.

    This message is the one that is edited when the roster is updated.
    Each guild can only have one roster message at a time.
    """
    doc = await get_guild_doc(guild)
    doc["roster_message"] = {"channel_id": message.channel.id, "id": message.id}
    db.update(doc, doc_ids=[guild.id])


async def get_roster_message_id(guild: discord.Guild) -> RosterMessageInfo | None:
    """Get the roster message ID from the datastore."""
    # Get the message ID from tinydb
    doc = db.get(doc_id=guild.id)
    if doc is None:
        return None

    assert isinstance(doc, Document)

    message = doc.get("roster_message")

    if message is None:
        return None

    return {
        "guild_id": guild.id,
        "channel_id": message["channel_id"],
        "id": message["id"],
    }


OBSERVERS: dict[int, typing.Callable[[dict[str, str]], typing.Awaitable]] = {}


async def register_status_observer(
    guild: discord.Guild,
    callback: typing.Callable[[dict[str, str]], typing.Awaitable],
):
    """Register an roster to be notified when a member's status changes.

    There can only be one observer per guild.
    """
    OBSERVERS[guild.id] = callback


async def update_member_status(
    guild: discord.Guild, member: discord.Member, status: str, quiet: bool = False
):
    """Update the member's status."""
    doc = await get_guild_doc(guild)

    member_statuses = doc.get("member_statuses", {})

    member_statuses[str(member.id)] = status

    doc["member_statuses"] = member_statuses

    db.update(doc, doc_ids=[guild.id])

    # Notify the observer
    if not quiet:
        await OBSERVERS[guild.id](member_statuses)


async def remove_member(guild: discord.Guild, member: discord.Member):
    """Remove a member from the roster."""
    doc = await get_guild_doc(guild)
    member_statuses = doc.get("member_statuses", {})

    member_statuses.pop(str(member.id), None)

    db.update(doc, doc_ids=[guild.id])

    # Notify the observer
    await OBSERVERS[guild.id](member_statuses)


async def reset_members(guild: discord.Guild):
    """Reset the member statuses."""
    doc = await get_guild_doc(guild)
    doc["member_statuses"] = {}
    db.update(doc, doc_ids=[guild.id])
    await OBSERVERS[guild.id]({})


async def get_member_statues(guild: discord.Guild) -> dict[str, str]:
    """Get the member statuses."""
    doc = await get_guild_doc(guild)
    return doc.get("member_statuses", {})
