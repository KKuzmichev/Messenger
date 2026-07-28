import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.message import AttachmentMeta, CursorPage, MessageResponse, SendMessageRequest
from app.services import conversation as conv_service
from app.services import message as msg_service

router = APIRouter(prefix="/api/conversations", tags=["messages"])


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    member_ids = await conv_service.get_conversation_member_ids(db, conv.id)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    msg = await msg_service.send_message(
        db,
        conversation_id=str(conv.id),
        sender_id=user_id,
        ciphertext=bytes.fromhex(body.ciphertext),
        iv=bytes.fromhex(body.iv),
        salt=bytes.fromhex(body.salt),
        ephemeral_key=bytes.fromhex(body.ephemeral_key) if body.ephemeral_key else None,
        key_id=body.key_id,
        attachment_ids=body.attachment_ids,
    )

    attachments = await msg_service.get_message_attachments(db, msg.id)
    return MessageResponse(
        id=str(msg.id),
        conversation_id=str(msg.conversation_id),
        sender_id=str(msg.sender_id) if msg.sender_id else None,
        ciphertext=msg.ciphertext.hex(),
        iv=msg.iv.hex(),
        salt=msg.salt.hex(),
        ephemeral_key=msg.ephemeral_key.hex() if msg.ephemeral_key else None,
        key_id=msg.key_id,
        created_at=msg.created_at,
        attachments=[AttachmentMeta(id=str(a.id), filename=a.filename, mime_type=a.mime_type, size=a.size, content_hash=a.content_hash.hex()) for a in attachments],
    )


@router.get("/{conversation_id}/messages", response_model=CursorPage)
async def get_messages(
    conversation_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(50, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    member_ids = await conv_service.get_conversation_member_ids(db, conv.id)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    messages, next_cursor = await msg_service.get_messages(db, conversation_id, cursor, limit)

    items = []
    for msg in messages:
        attachments = await msg_service.get_message_attachments(db, msg.id)
        items.append(MessageResponse(
            id=str(msg.id),
            conversation_id=str(msg.conversation_id),
            sender_id=str(msg.sender_id) if msg.sender_id else None,
            ciphertext=msg.ciphertext.hex(),
            iv=msg.iv.hex(),
            salt=msg.salt.hex(),
            ephemeral_key=msg.ephemeral_key.hex() if msg.ephemeral_key else None,
            key_id=msg.key_id,
            created_at=msg.created_at,
            attachments=[AttachmentMeta(id=str(a.id), filename=a.filename, mime_type=a.mime_type, size=a.size, content_hash=a.content_hash.hex()) for a in attachments],
        ))

    return CursorPage(items=items, next_cursor=next_cursor, has_more=next_cursor is not None)


@router.post("/{conversation_id}/messages/{message_id}/read")
async def mark_read(
    conversation_id: str,
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    member_ids = await conv_service.get_conversation_member_ids(db, conv.id)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    await msg_service.create_read_receipt(db, user_id, message_id)
    return {"status": "ok"}
