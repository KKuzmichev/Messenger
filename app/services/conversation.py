import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.participant import Participant


def _to_uuid(s: str) -> uuid.UUID:
    return uuid.UUID(s)


async def create_conversation(
    db: AsyncSession, conv_type: str, member_ids: list[str], creator_id: str
) -> Conversation:
    creator_uuid = _to_uuid(creator_id)

    if conv_type == "self":
        existing = await _find_self_conversation(db, creator_uuid)
        if existing:
            return existing
        member_uuids = [creator_uuid]
    elif conv_type == "direct":
        member_uuids = [_to_uuid(m) for m in member_ids]
        existing = await _find_direct_conversation(db, member_uuids)
        if existing:
            return existing
        member_uuids = list(set(member_uuids + [creator_uuid]))
    else:
        member_uuids = list(set([_to_uuid(m) for m in member_ids] + [creator_uuid]))

    conv = Conversation(type=conv_type)
    db.add(conv)
    await db.flush()

    for uid in member_uuids:
        db.add(Participant(conversation_id=conv.id, user_id=uid))

    await db.commit()
    await db.refresh(conv)
    return conv


async def _find_self_conversation(db: AsyncSession, user_uuid: uuid.UUID) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.type == "self",
            Conversation.id.in_(
                select(Participant.conversation_id).where(Participant.user_id == user_uuid)
            ),
        )
    )
    return result.scalar_one_or_none()


async def _find_direct_conversation(db: AsyncSession, member_uuids: list[uuid.UUID]) -> Conversation | None:
    if len(member_uuids) != 2:
        return None

    result = await db.execute(
        select(Conversation).where(Conversation.type == "direct")
    )
    for conv in result.scalars().all():
        members = await get_conversation_member_ids(db, conv.id)
        if sorted(members) == sorted([str(m) for m in member_uuids]):
            return conv
    return None


async def get_conversation_member_ids(db: AsyncSession, conversation_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(Participant.user_id).where(Participant.conversation_id == conversation_id)
    )
    return [str(row[0]) for row in result.all()]


async def get_user_conversations(db: AsyncSession, user_id: str) -> list[Conversation]:
    subq = select(Participant.conversation_id).where(Participant.user_id == _to_uuid(user_id))
    result = await db.execute(
        select(Conversation).where(Conversation.id.in_(subq)).order_by(Conversation.created_at.desc())
    )
    return list(result.scalars().all())


async def get_last_message(db: AsyncSession, conversation_id: uuid.UUID) -> Message | None:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_conversation(db: AsyncSession, conversation_id: str) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.id == _to_uuid(conversation_id)))
    return result.scalar_one_or_none()


async def add_member(db: AsyncSession, conversation_id: str, user_id: str) -> Participant | None:
    conv = await get_conversation(db, conversation_id)
    if not conv or conv.type != "group":
        return None

    user_uuid = _to_uuid(user_id)
    result = await db.execute(
        select(Participant).where(
            Participant.conversation_id == conv.id,
            Participant.user_id == user_uuid,
        )
    )
    if result.scalar_one_or_none():
        return None

    participant = Participant(conversation_id=conv.id, user_id=user_uuid)
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant


async def remove_member(db: AsyncSession, conversation_id: str, user_id: str) -> bool:
    conv_uuid = _to_uuid(conversation_id)
    user_uuid = _to_uuid(user_id)
    result = await db.execute(
        delete(Participant).where(
            Participant.conversation_id == conv_uuid,
            Participant.user_id == user_uuid,
        )
    )
    await db.commit()
    return result.rowcount > 0
