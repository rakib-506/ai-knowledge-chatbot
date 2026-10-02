"""Knowledge base management (admins only): upload files, add web pages, list and delete documents."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query

from .. import database as db
from .. import knowledge_base as kb
from ..auth import require_admin
from ..config import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, UPLOAD_DIR, GEMINI_MODEL
from ..loaders import load_url
from ..logger import log, read_last_lines
from ..schemas import DocumentOut, UploadResult, UrlRequest, StatsOut, UserOut

router = APIRouter(prefix="/api/admin", tags=["Admin: Knowledge Base"])


@router.post("/documents/upload", response_model=UploadResult, summary="Upload files (PDF, TXT, MD, DOCX, HTML)")
async def upload(files: list[UploadFile] = File(...), admin: dict = Depends(require_admin)):
    """Adds files to the knowledge base right away. No retraining needed.
    A file with the same name replaces the old version."""
    added, errors = [], []
    for f in files:
        name = Path(f.filename or "file").name
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"{name}: type {ext or '(none)'} is not supported.")
            continue
        data = await f.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            errors.append(f"{name}: file is larger than {MAX_UPLOAD_MB} MB.")
            continue
        try:
            (UPLOAD_DIR / name).write_bytes(data)
            added.append(kb.add_file(name, data, added_by=admin["username"]))
        except Exception as e:
            log.error(f"Upload failed for '{name}': {e}")
            errors.append(f"{name}: {e}")
    return {"added": added, "errors": errors}


@router.post("/documents/url", response_model=DocumentOut, summary="Add a web page by URL")
def add_url(body: UrlRequest, admin: dict = Depends(require_admin)):
    try:
        text = load_url(body.url)
    except Exception as e:
        log.error(f"Could not read URL {body.url}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not read this web page: {e}")
    try:
        return kb.add_text(body.url, text, "web", added_by=admin["username"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents", response_model=list[DocumentOut], summary="List all documents")
def list_documents(admin: dict = Depends(require_admin)):
    return db.list_documents()


@router.delete("/documents/{doc_id}", summary="Delete a document")
def delete_document(doc_id: str, admin: dict = Depends(require_admin)):
    if not kb.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": doc_id}


@router.post("/documents/reload-folder", summary="Load all files from the /knowledge_base folder")
def reload_folder(admin: dict = Depends(require_admin)):
    count = kb.load_starter_folder(force=True)
    return {"loaded": count}


@router.get("/stats", response_model=StatsOut, summary="Knowledge base and usage numbers")
def stats(admin: dict = Depends(require_admin)):
    return {"documents": db.count_rows("documents"), "chunks": kb.total_chunks(),
            "users": db.count_rows("users"), "chats": db.count_rows("sessions"),
            "messages": db.count_rows("messages"), "model": GEMINI_MODEL}


@router.get("/users", response_model=list[UserOut], summary="List users")
def users(admin: dict = Depends(require_admin)):
    return db.list_users()


@router.get("/logs", summary="Read the last lines of the backend log")
def logs(lines: int = Query(100, ge=1, le=1000), admin: dict = Depends(require_admin)):
    return {"lines": read_last_lines(lines)}
