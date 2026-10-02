"""Chat endpoints: ask questions and manage chat sessions (conversation memory)."""
import json

from fastapi import APIRouter, Depends, HTTPException

from .. import database as db
from .. import chat as chat_service
from ..auth import get_current_user
from ..llm import LLMError
from ..schemas import ChatRequest, ChatResponse, SessionOut, MessageOut

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="Ask a question")
def ask(body: ChatRequest, user: dict = Depends(get_current_user)):
    """Answers using only the knowledge base. Send `session_id` to continue a chat (the bot remembers
    the last few messages). If the answer is not in the knowledge base, `found` is false."""
    try:
        return chat_service.answer(user, body.message, body.session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'"))
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions", response_model=list[SessionOut], summary="List my chats")
def sessions(user: dict = Depends(get_current_user)):
    return db.list_sessions(user["id"])


@router.get("/sessions/{session_id}", response_model=list[MessageOut], summary="Get all messages of a chat")
def messages(session_id: str, user: dict = Depends(get_current_user)):
    if db.get_session(session_id, user["id"]) is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    out = []
    for m in db.get_messages(session_id):
        meta = json.loads(m["sources"]) if m["sources"] else {}
        out.append({"role": m["role"], "content": m["content"], "created_at": m["created_at"],
                    "sources": meta.get("sources", []), "found": meta.get("found", True)})
    return out


@router.delete("/sessions/{session_id}", summary="Delete a chat")
def delete(session_id: str, user: dict = Depends(get_current_user)):
    if not db.delete_session(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {"deleted": session_id}
