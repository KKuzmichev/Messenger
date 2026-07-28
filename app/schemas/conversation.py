from datetime import datetime

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    type: str = Field(pattern=r"^(direct|group)$")
    member_ids: list[str] = Field(min_length=1)


class AddMemberRequest(BaseModel):
    user_id: str


class ConversationResponse(BaseModel):
    id: str
    type: str
    created_at: datetime
    member_ids: list[str] = []


class LastMessagePreview(BaseModel):
    id: str
    sender_id: str | None
    created_at: datetime


class ConversationListItem(BaseModel):
    id: str
    type: str
    created_at: datetime
    last_message: LastMessagePreview | None = None
