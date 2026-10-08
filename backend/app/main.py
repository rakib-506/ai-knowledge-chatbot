"""FastAPI application: connects all parts.

Run from the backend folder:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000 (chat app) and http://127.0.0.1:8000/docs (API docs).
"""
import time
from contextlib import asynccontextmanager
from .llm import get_active_model

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import database as db
from . import knowledge_base as kb
from .auth import ensure_admin_exists
from .config import FRONTEND_DIR, GEMINI_MODEL
from .logger import log
from .routers import auth, chat, knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting backend ...")
    db.init_db()
    ensure_admin_exists()
    log.info("Loading starter documents (the first start downloads a small embedding model) ...")
    loaded = kb.load_starter_folder()
    log.info(f"Ready. New starter documents loaded: {loaded}. Total chunks: {kb.total_chunks()}. "
             f"Model: {GEMINI_MODEL}")
    yield
    log.info("Backend stopped.")


app = FastAPI(
    title="Knowledge Chatbot API",
    version="1.0.0",
    description=(
        "Backend for an AI chatbot that answers **only** from its own knowledge base (RAG).\n\n"
        "**How to try it here:** click **Authorize**, log in with your username and password, "
        "then use the endpoints below.\n\n"
        "- **Authentication**: register and log in (JWT token).\n"
        "- **Chat**: ask questions; chats keep short-term memory.\n"
        "- **Admin: Knowledge Base**: add or remove documents without retraining (admins only)."
    ),
    lifespan=lifespan,
)

# The frontend may also be hosted on another address (for example port 5500).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        ms = (time.perf_counter() - start) * 1000
        log.info(f"{request.method} {request.url.path} -> {response.status_code} ({ms:.0f} ms)")
    return response


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": get_active_model()}

# Serve the frontend files (must be last, so /api routes win)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
