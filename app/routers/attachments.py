from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.attachment import (
    AttachmentDownloadResponse,
    AttachmentMetaResponse,
    AttachmentUploadResponse,
)
from app.services import attachment as att_service

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    content_hash: str = Form(...),
    iv: str = Form(...),
    salt: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()

    att, dedup = await att_service.upload_attachment(
        db,
        content_hash=bytes.fromhex(content_hash),
        filename=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
        size=len(data),
        ciphertext=data,
        iv=bytes.fromhex(iv),
        salt=bytes.fromhex(salt),
        uploader_id=user_id,
    )
    return AttachmentUploadResponse(id=str(att.id), dedup=dedup)


@router.get("/{attachment_id}", response_model=AttachmentDownloadResponse)
async def download_attachment(
    attachment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    att = await att_service.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return AttachmentDownloadResponse(
        id=str(att.id),
        filename=att.filename,
        mime_type=att.mime_type,
        size=att.size,
        content_hash=att.content_hash.hex(),
        ciphertext=att.ciphertext.hex(),
        iv=att.iv.hex(),
        salt=att.salt.hex(),
    )


@router.get("/{attachment_id}/meta", response_model=AttachmentMetaResponse)
async def get_attachment_meta(
    attachment_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    att = await att_service.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return AttachmentMetaResponse(
        id=str(att.id),
        filename=att.filename,
        mime_type=att.mime_type,
        size=att.size,
        content_hash=att.content_hash.hex(),
    )
