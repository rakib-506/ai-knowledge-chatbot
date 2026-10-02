"""Knowledge base: split documents into chunks, store them in ChromaDB, and search them.

Embeddings are made locally by ChromaDB's default model (all-MiniLM-L6-v2, about 80 MB,
downloaded once on first use). So adding documents needs no API calls and no retraining.
"""
import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from . import database as db
from .config import DATA_DIR, CHUNK_WORDS, CHUNK_OVERLAP, TOP_K, KNOWLEDGE_DIR, ALLOWED_EXTENSIONS
from .loaders import load_file
from .logger import log

COLLECTION_NAME = "knowledge"
_client = None
_collection = None
embedding_function = None   # can be replaced in tests


def get_collection():
    global _client, _collection, embedding_function
    if _collection is None:
        if embedding_function is None:
            embedding_function = embedding_functions.DefaultEmbeddingFunction()
        _client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"),
                                            settings=Settings(anonymized_telemetry=False))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},     # cosine distance: 0 = same meaning
        )
    return _collection


# ---------- chunking ----------
def chunk_text(text: str, chunk_words: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word windows (same idea as the Assignment 2 chunker)."""
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    step = max(1, chunk_words - overlap)
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def _title(name: str) -> str:
    return Path(name).stem.replace("_", " ").replace("-", " ") if "://" not in name else name


# ---------- add / delete ----------
def add_text(name: str, text: str, source_type: str, added_by: str = "system") -> dict:
    """Add (or replace) one document. Returns the document record."""
    if len(text.split()) < 5:
        raise ValueError("No readable text found in this document.")

    old = db.get_document_by_name(name)
    if old:                                   # same name -> update instead of duplicate
        delete_document(old["id"])
        log.info(f"Replacing existing document '{name}'")

    doc_id = uuid.uuid4().hex[:12]
    chunks = chunk_text(text)
    title = _title(name)
    get_collection().add(
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        documents=[f"{title}\n{c}" for c in chunks],
        metadatas=[{"doc_id": doc_id, "source": name, "chunk": i} for i in range(len(chunks))],
    )
    db.add_document(doc_id, name, source_type, len(chunks), len(text.split()), added_by)
    log.info(f"Added document '{name}' ({source_type}): {len(chunks)} chunks, {len(text.split())} words")
    return dict(db.get_document(doc_id))


def add_file(filename: str, data: bytes, added_by: str = "system") -> dict:
    text = load_file(filename, data)
    return add_text(filename, text, Path(filename).suffix.lower().lstrip("."), added_by)


def delete_document(doc_id: str) -> bool:
    if db.get_document(doc_id) is None:
        return False
    get_collection().delete(where={"doc_id": doc_id})
    db.delete_document_row(doc_id)
    log.info(f"Deleted document {doc_id}")
    return True


def load_starter_folder(force: bool = False) -> int:
    """Load every supported file in /knowledge_base. Skips files already loaded unless force=True."""
    count = 0
    if not KNOWLEDGE_DIR.exists():
        return 0
    for path in sorted(KNOWLEDGE_DIR.iterdir()):
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if not force and db.get_document_by_name(path.name):
            continue
        try:
            add_file(path.name, path.read_bytes(), added_by="starter-folder")
            count += 1
        except Exception as e:
            log.error(f"Could not load '{path.name}': {e}")
    return count


# ---------- search ----------
def search(query: str, top_k: int = TOP_K) -> list[dict]:
    """Return the top_k most similar chunks with a similarity score (1 = same meaning)."""
    col = get_collection()
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(top_k, col.count()))
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"text": text, "source": meta["source"], "chunk": meta["chunk"],
                     "similarity": round(1 - dist, 3)})
    return hits


def total_chunks() -> int:
    return get_collection().count()
