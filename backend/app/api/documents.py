"""Document upload and management endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.config import get_settings
from app.models import Document
from app.rag.extract import ALLOWED_EXTENSIONS
from app.rag.ingest import delete_document_data, ingest_document
from app.schemas import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
async def list_documents(user: CurrentUser, db: DB) -> list[DocumentOut]:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentOut.model_validate(d) for d in result.scalars().all()]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile, user: CurrentUser, db: DB
) -> DocumentOut:
    settings = get_settings()
    filename = (file.filename or "upload").strip()
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS)),
        )
    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.max_upload_mb} MB.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty."
        )

    document = Document(
        user_id=user.id,
        filename=filename[:255],
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Ingest synchronously so the client gets the definitive status back.
    # Extraction and embedding for a 10 MB cap completes in a few seconds.
    await ingest_document(db, document, data)
    await db.refresh(document)
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, user: CurrentUser, db: DB) -> None:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    await delete_document_data(db, document)
