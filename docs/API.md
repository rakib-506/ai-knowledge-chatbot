# API Documentation

The backend is a REST API built with FastAPI.

- **Interactive docs (Swagger):** http://127.0.0.1:8000/docs. You can try every endpoint here. Click **Authorize** and log in first.
- **Alternative docs (ReDoc):** http://127.0.0.1:8000/redoc
- **OpenAPI JSON:** http://127.0.0.1:8000/openapi.json

All endpoints except `register`, `login` and `health` need a token:

```
Authorization: Bearer <access_token>
```

## Authentication

| Method | Path | Who | What it does |
|---|---|---|---|
| POST | `/api/auth/register` | anyone | Create a user account. Body: `{"username", "password"}`. Returns a token. |
| POST | `/api/auth/login` | anyone | Log in. **Form data:** `username`, `password`. Returns a token. |
| GET | `/api/auth/me` | user | Get the logged-in user. |

**Login response example**

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer", "username": "rakib", "role": "user" }
```

## Chat

| Method | Path | Who | What it does |
|---|---|---|---|
| POST | `/api/chat` | user | Ask a question. Body: `{"message", "session_id"}`. Leave `session_id` empty to start a new chat. |
| GET | `/api/chat/sessions` | user | List my chats. |
| GET | `/api/chat/sessions/{id}` | user | Get all messages of one chat. |
| DELETE | `/api/chat/sessions/{id}` | user | Delete a chat. |

**Request**

```json
{ "message": "How much is a single room in the hostel?", "session_id": null }
```

**Response (answer found)**

```json
{
  "session_id": "3f1c...",
  "answer": "A single room costs 9,000 Taka per month...",
  "found": true,
  "type": "answer",
  "sources": [ { "source": "hostel_guide.txt", "similarity": 0.62 } ],
  "search_query": "How much is a single room in the hostel?"
}
```

**Response (not in the knowledge base)**

```json
{
  "answer": "Sorry, I couldn't find that in my knowledge base. Could you rephrase your question? ...",
  "found": false,
  "type": "not_found",
  "sources": []
}
```

`type` is one of: `answer`, `not_found`, `small_talk`.

## Admin: knowledge base (admins only)

| Method | Path | What it does |
|---|---|---|
| POST | `/api/admin/documents/upload` | Upload one or more files (multipart field `files`). PDF, TXT, MD, DOCX, HTML. Max 10 MB each. |
| POST | `/api/admin/documents/url` | Add a web page. Body: `{"url": "https://..."}` |
| GET | `/api/admin/documents` | List all documents. |
| DELETE | `/api/admin/documents/{id}` | Delete a document (and all its chunks). |
| POST | `/api/admin/documents/reload-folder` | Load all files from the `knowledge_base/` folder again. |
| GET | `/api/admin/stats` | Numbers: documents, chunks, users, chats, messages, model. |
| GET | `/api/admin/users` | List users. |
| GET | `/api/admin/logs?lines=100` | Last lines of the backend log. |

## System

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Check that the backend is running. |

## Error format

Errors always look like this:

```json
{ "detail": "Wrong username or password." }
```

| Code | Meaning |
|---|---|
| 400 | Bad input (for example, the web page could not be read) |
| 401 | Not logged in, or the token expired |
| 403 | Admins only |
| 404 | Not found |
| 409 | Username already taken |
| 422 | Missing or wrong fields |
| 503 | The AI service is busy or not set up (see the message) |
