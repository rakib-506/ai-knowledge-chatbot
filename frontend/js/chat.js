auth.requireLogin();

// Example questions shown in an empty chat. Change these to match your knowledge base.
const SUGGESTIONS = [
  "What GPA do I need to apply?",
  "How much is a single room in the hostel?",
  "What are the library opening hours on Friday?",
  "Which scholarships are there for new students?",
];

const thread = document.getElementById("thread");
const messagesBox = document.getElementById("messages");
const input = document.getElementById("message");
const sendBtn = document.getElementById("send");
const sessionList = document.getElementById("session-list");
const titleEl = document.getElementById("chat-title");
const sidebar = document.getElementById("sidebar");
let currentSession = null;
let busy = false;

// ---------- user area ----------
const user = auth.user || {};
document.getElementById("who").textContent = `${user.username || ""}${user.role === "admin" ? " · admin" : ""}`;
if (user.role === "admin") document.getElementById("admin-link").classList.remove("hidden");
document.getElementById("logout").onclick = auth.logout;
document.getElementById("menu-btn").onclick = () => sidebar.classList.toggle("open");

// ---------- rendering ----------
function scrollDown() { messagesBox.scrollTop = messagesBox.scrollHeight; }

function showWelcome() {
  thread.innerHTML = `
    <div class="welcome">
      <h1>What would you like to know?</h1>
      <p>I answer only from the documents in the knowledge base. If the answer is not there, I'll tell you.</p>
      <div class="suggestions">${SUGGESTIONS.map(s => `<button class="suggestion">${escapeHtml(s)}</button>`).join("")}</div>
    </div>`;
  thread.querySelectorAll(".suggestion").forEach(b => b.onclick = () => send(b.textContent));
}

function addUser(text) {
  thread.querySelector(".welcome")?.remove();
  const div = document.createElement("div");
  div.className = "msg msg-user";
  div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  thread.appendChild(div);
  scrollDown();
}

function addBot(text, { sources = [], found = true, error = false } = {}) {
  const div = document.createElement("div");
  div.className = "msg msg-bot" + (error ? " error" : !found ? " not-found" : "");
  const flag = !found && !error ? `<div class="flag">Not in the knowledge base</div>` : "";
  const src = sources.length
    ? `<div class="sources"><span class="sources-label">From</span>${sources.map(s =>
        `<span class="source" title="Match ${Math.round(s.similarity * 100)}%">
           <span class="source-type">${fileType(s.source)}</span>${escapeHtml(s.source)}
           <span class="source-score">${Math.round(s.similarity * 100)}%</span></span>`).join("")}</div>`
    : "";
  div.innerHTML = `<div class="body">${flag}${renderMarkdown(text)}</div>${src}`;
  thread.appendChild(div);
  scrollDown();
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg msg-bot";
  div.innerHTML = `<div class="typing">Searching the documents</div>`;
  thread.appendChild(div);
  scrollDown();
  return div;
}

// ---------- sessions ----------
async function loadSessions() {
  const sessions = await api("/api/chat/sessions");
  sessionList.innerHTML = sessions.length ? "" : `<li class="sidebar-empty">No chats yet</li>`;
  for (const s of sessions) {
    const li = document.createElement("li");
    if (s.id === currentSession) li.classList.add("active");
    li.innerHTML = `<button class="session-open">${escapeHtml(s.title)}</button>
                    <button class="session-del" aria-label="Delete chat" title="Delete chat">✕</button>`;
    li.querySelector(".session-open").onclick = () => openSession(s.id, s.title);
    li.querySelector(".session-del").onclick = () => deleteSession(s.id);
    sessionList.appendChild(li);
  }
}

async function openSession(id, title) {
  currentSession = id;
  titleEl.textContent = title;
  sidebar.classList.remove("open");
  thread.innerHTML = "";
  const msgs = await api(`/api/chat/sessions/${id}`);
  for (const m of msgs) {
    if (m.role === "user") addUser(m.content);
    else addBot(m.content, { sources: m.sources, found: m.found });
  }
  loadSessions();
}

async function deleteSession(id) {
  if (!confirm("Delete this chat?")) return;
  await api(`/api/chat/sessions/${id}`, { method: "DELETE" });
  if (id === currentSession) newChat();
  loadSessions();
}

function newChat() {
  currentSession = null;
  titleEl.textContent = "New chat";
  sidebar.classList.remove("open");
  showWelcome();
  loadSessions();
  input.focus();
}
document.getElementById("new-chat").onclick = newChat;

// ---------- sending ----------
async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  sendBtn.disabled = true;
  input.value = "";
  autoGrow();
  addUser(text);
  const typing = addTyping();
  try {
    const res = await api("/api/chat", { method: "POST", json: { message: text, session_id: currentSession } });
    typing.remove();
    addBot(res.answer, { sources: res.sources, found: res.found });
    if (!currentSession) {
      currentSession = res.session_id;
      titleEl.textContent = text.slice(0, 60);
      loadSessions();
    }
  } catch (err) {
    typing.remove();
    addBot(err.message, { error: true });
  } finally {
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

document.getElementById("chat-form").addEventListener("submit", e => { e.preventDefault(); send(input.value); });
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
});
function autoGrow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }
input.addEventListener("input", autoGrow);

showWelcome();
loadSessions().catch(err => addBot(err.message, { error: true }));
