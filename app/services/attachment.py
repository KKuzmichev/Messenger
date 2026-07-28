import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


async def upload_attachment(
    db: AsyncSession,
    content_hash: bytes,
    filename: str,
    mime_type: str,
    size: int,
    ciphertext: bytes,
    iv: bytes,
    salt: bytes,
    uploader_id: str,
) -> tuple[Attachment, bool]:
    result = await db.execute(select(Attachment).where(Attachment.content_hash == content_hash))
    existing = result.scalar_one_or_none()
    if existing:
        return existing, True

    att = Attachment(
        content_hash=content_hash,
        filename=filename,
        mime_type=mime_type,
        size=size,
        ciphertext=ciphertext,
        iv=iv,
        salt=salt,
        uploader_id=uuid.UUID(uploader_id),
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att, False


async def get_attachment(db: AsyncSession, attachment_id: str) -> Attachment | None:
    result = await db.execute(select(Attachment).where(Attachment.id == uuid.UUID(attachment_id)))
    return result.scalar_one_or_none()
