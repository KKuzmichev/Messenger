import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment, MessageAttachment
from app.models.message import Message


async def send_message(
    db: AsyncSession,
    conversation_id: str,
    sender_id: str,
    ciphertext: bytes,
    iv: bytes,
    salt: bytes,
    ephemeral_key: bytes | None,
    key_id: str | None,
    attachment_ids: list[str],
) -> Message:
    msg = Message(
        conversation_id=uuid.UUID(conversation_id),
        sender_id=uuid.UUID(sender_id),
        ciphertext=ciphertext,
        iv=iv,
        salt=salt,
        ephemeral_key=ephemeral_key,
        key_id=key_id,
    )
    db.add(msg)
    await db.flush()

    for att_id in attachment_ids:
        db.add(MessageAttachment(message_id=msg.id, attachment_id=uuid.UUID(att_id)))

    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(
    db: AsyncSession,
    conversation_id: str,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[Message], str | None]:
    conv_uuid = uuid.UUID(conversation_id)
    query = select(Message).where(Message.conversation_id == conv_uuid).order_by(Message.created_at.desc()).limit(limit + 1)

    if cursor:
        query = query.where(Message.created_at < cursor)

    result = await db.execute(query)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = str(rows[-1].created_at.isoformat()) if rows and has_more else None
    return rows, next_cursor


async def get_message_attachments(db: AsyncSession, message_id: uuid.UUID) -> list[Attachment]:
    result = await db.execute(
        select(Attachment).join(MessageAttachment).where(MessageAttachment.message_id == message_id)
    )
    return list(result.scalars().all())


async def create_read_receipt(db: AsyncSession, user_id: str, message_id: str) -> None:
    from app.models.read_receipt import ReadReceipt

    rr = ReadReceipt(user_id=uuid.UUID(user_id), message_id=uuid.UUID(message_id))
    await db.merge(rr)
    await db.commit()
