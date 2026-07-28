from datetime import datetime

from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    ciphertext: str
    iv: str
    salt: str
    ephemeral_key: str | None = None
    key_id: str | None = None
    attachment_ids: list[str] = []


class AttachmentMeta(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    content_hash: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str | None
    ciphertext: str
    iv: str
    salt: str
    ephemeral_key: str | None
    key_id: str | None
    created_at: datetime
    attachments: list[AttachmentMeta] = []


class CursorPage(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None
    has_more: bool
