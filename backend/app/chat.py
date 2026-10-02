"""The chat pipeline (RAG = Retrieval-Augmented Generation).

1. Small talk ("hi", "thanks")  -> friendly reply, no search.
2. Follow-up question           -> rewrite it into a full question using chat memory.
3. Search the knowledge base    -> keep only chunks that are similar enough.
4. Nothing relevant             -> polite "not found" reply (no guessing).
5. Ask Gemini to answer ONLY from the found chunks. If Gemini says NOT_FOUND -> polite reply.
"""
import json
import re
from pathlib import Path

from . import database as db
from . import knowledge_base as kb
from . import llm
from .config import MIN_SIMILARITY, MEMORY_MESSAGES, REWRITE_FOLLOWUPS
from .logger import log

SYSTEM_PROMPT = """You are a helpful knowledge assistant. You answer ONLY with facts from the CONTEXT.
Rules:
1. Use only the CONTEXT. Never use outside knowledge, even if you know the answer.
2. If the CONTEXT does not contain the answer, reply with exactly: NOT_FOUND
3. If only part of the answer is in the CONTEXT, give that part and say the rest is not in the documents.
4. Use the CHAT HISTORY only to understand what the user means (for example "it" or "that one").
5. Keep answers short and clear. Use bullet points for lists.
6. Do not talk about "context" or "chunks". You may say "according to our documents"."""

REWRITE_PROMPT = """Rewrite the LAST QUESTION so it can be understood without the chat history.
Replace words like "it", "that", "they" with what they mean. If it is already clear, return it unchanged.
Return only the rewritten question, nothing else.

CHAT HISTORY:
{history}

LAST QUESTION: {question}"""

SMALL_TALK = [
    (r"^(hi|hello|hey|hii+|salam|assalamu ?alaikum|good (morning|afternoon|evening))\b",
     "Hello! Ask me anything about the documents in my knowledge base."),
    (r"^(thanks|thank you|thx|ok thanks)\b", "You're welcome! Ask me anything else."),
    (r"^(bye|goodbye|see you)\b", "Goodbye! Come back any time."),
    (r"^(who are you|what can you do|help)\b",
     "I am a knowledge assistant. I answer questions using only the documents in my knowledge base. "
     "If I can't find something, I'll tell you."),
]


def _small_talk(message: str):
    text = message.strip().lower()
    if len(text.split()) > 6:
        return None
    for pattern, reply in SMALL_TALK:
        if re.match(pattern, text):
            return reply
    return None


def _topics() -> list[str]:
    names = []
    for d in db.list_documents():
        n = d["name"]
        names.append(n if "://" in n else Path(n).stem.replace("_", " ").replace("-", " ").title())
    return names[:6]


def fallback_message() -> str:
    topics = _topics()
    if not topics:
        return "My knowledge base is empty right now. Please ask an admin to add some documents."
    return ("Sorry, I couldn't find that in my knowledge base. Could you rephrase your question? "
            "I can help with topics like: " + ", ".join(topics) + ".")


def _history_text(history: list[dict]) -> str:
    return "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in history)


def _search_query(message: str, history: list[dict]) -> str:
    if not history:
        return message
    if REWRITE_FOLLOWUPS:
        try:
            rewritten = llm.generate(REWRITE_PROMPT.format(history=_history_text(history), question=message),
                                     temperature=0)
            if rewritten:
                return rewritten.splitlines()[0].strip()
        except llm.LLMError:
            pass
    # cheap backup: add the previous user question to the search
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    return f"{last_user} {message}".strip()


def answer(user: dict, message: str, session_id: str | None = None) -> dict:
    message = message.strip()

    # ---- session (conversation memory) ----
    if session_id and db.get_session(session_id, user["id"]) is None:
        raise KeyError("Chat session not found.")
    if not session_id:
        session_id = db.create_session(user["id"], title=message)
    history = db.get_messages(session_id, limit=MEMORY_MESSAGES)

    # ---- 1. small talk ----
    reply = _small_talk(message)
    if reply:
        return _save(session_id, message, reply, [], found=True, kind="small_talk", search_query=None)

    # ---- 2. + 3. retrieval ----
    query = _search_query(message, history)
    hits = kb.search(query)
    relevant = [h for h in hits if h["similarity"] >= MIN_SIMILARITY]
    log.info(f"user={user['username']} q='{message[:80]}' search='{query[:80]}' "
             f"best_sim={hits[0]['similarity'] if hits else None} relevant={len(relevant)}")

    # ---- 4. nothing relevant -> fallback ----
    if not relevant:
        return _save(session_id, message, fallback_message(), [], found=False, kind="not_found", search_query=query)

    # ---- 5. grounded answer ----
    context = "\n\n".join(f"[{i + 1}] (from {h['source']})\n{h['text']}" for i, h in enumerate(relevant))
    prompt = (f"CHAT HISTORY:\n{_history_text(history) or '(none)'}\n\n"
              f"CONTEXT:\n{context}\n\n"
              f"QUESTION: {message}")
    text = llm.generate(prompt, system=SYSTEM_PROMPT)

    if not text or "NOT_FOUND" in text:
        return _save(session_id, message, fallback_message(), [], found=False, kind="not_found", search_query=query)

    sources = {}
    for h in relevant:   # one entry per document, keep the best score
        if h["source"] not in sources or h["similarity"] > sources[h["source"]]:
            sources[h["source"]] = h["similarity"]
    source_list = [{"source": s, "similarity": v} for s, v in sorted(sources.items(), key=lambda x: -x[1])]
    return _save(session_id, message, text, source_list, found=True, kind="answer", search_query=query)


def _save(session_id, question, reply, sources, found, kind, search_query) -> dict:
    db.add_message(session_id, "user", question)
    db.add_message(session_id, "assistant", reply, json.dumps({"sources": sources, "found": found}))
    if kind == "not_found":
        log.info(f"Fallback reply (not in knowledge base) for: '{question[:80]}'")
    return {"session_id": session_id, "answer": reply, "found": found, "type": kind,
            "sources": sources, "search_query": search_query}
