from pydantic import BaseModel


class AttachmentUploadResponse(BaseModel):
    id: str
    dedup: bool = False


class AttachmentMetaResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    content_hash: str


class AttachmentDownloadResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    content_hash: str
    ciphertext: str
    iv: str
    salt: str
