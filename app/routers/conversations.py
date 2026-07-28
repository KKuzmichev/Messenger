import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.conversation import (
    AddMemberRequest,
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    LastMessagePreview,
)
from app.services import conversation as conv_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv = await conv_service.create_conversation(db, body.type, body.member_ids, user_id)
    member_ids = await conv_service.get_conversation_member_ids(db, conv.id)
    return ConversationResponse(id=str(conv.id), type=conv.type, created_at=conv.created_at, member_ids=member_ids)


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    convs = await conv_service.get_user_conversations(db, user_id)
    items = []
    for conv in convs:
        last = await conv_service.get_last_message(db, conv.id)
        preview = None
        if last:
            preview = LastMessagePreview(id=str(last.id), sender_id=str(last.sender_id) if last.sender_id else None, created_at=last.created_at)
        items.append(ConversationListItem(id=str(conv.id), type=conv.type, created_at=conv.created_at, last_message=preview))
    return items


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = uuid.UUID(conversation_id)
    conv = await conv_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    member_ids = await conv_service.get_conversation_member_ids(db, conv_uuid)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    return ConversationResponse(id=str(conv.id), type=conv.type, created_at=conv.created_at, member_ids=member_ids)


@router.post("/{conversation_id}/members", status_code=201)
async def add_member(
    conversation_id: str,
    body: AddMemberRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = uuid.UUID(conversation_id)
    member_ids = await conv_service.get_conversation_member_ids(db, conv_uuid)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    participant = await conv_service.add_member(db, conversation_id, body.user_id)
    if participant is None:
        raise HTTPException(status_code=400, detail="Cannot add member or already a member")
    return {"status": "ok"}


@router.delete("/{conversation_id}/members/{target_user_id}")
async def remove_member(
    conversation_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = uuid.UUID(conversation_id)
    member_ids = await conv_service.get_conversation_member_ids(db, conv_uuid)
    if user_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member")

    removed = await conv_service.remove_member(db, conversation_id, target_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"status": "ok"}
