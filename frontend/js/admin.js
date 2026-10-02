auth.requireLogin();
if ((auth.user || {}).role !== "admin") window.location.href = "chat.html";
document.getElementById("logout").onclick = auth.logout;

const rows = document.getElementById("doc-rows");

function setStatus(el, text, ok = true) {
  el.textContent = text;
  el.className = "status " + (ok ? "ok" : "err");
}

async function loadStats() {
  const s = await api("/api/admin/stats");
  document.getElementById("s-docs").textContent = s.documents;
  document.getElementById("s-chunks").textContent = s.chunks;
  document.getElementById("s-users").textContent = s.users;
  document.getElementById("s-chats").textContent = s.chats;
}

async function loadDocs() {
  const docs = await api("/api/admin/documents");
  rows.innerHTML = docs.length ? "" :
    `<tr><td colspan="6">No documents yet. Add a file or a web page above.</td></tr>`;
  for (const d of docs) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="name">${escapeHtml(d.name)}</td>
      <td>${escapeHtml(d.source_type.toUpperCase())}</td>
      <td>${d.words.toLocaleString()}</td>
      <td>${d.chunks}</td>
      <td>${escapeHtml(d.added_by || "")}</td>
      <td><button class="btn-danger">Delete</button></td>`;
    tr.querySelector("button").onclick = async () => {
      if (!confirm(`Delete "${d.name}" from the knowledge base?`)) return;
      await api(`/api/admin/documents/${d.id}`, { method: "DELETE" });
      refreshAll();
    };
    rows.appendChild(tr);
  }
}

async function loadLogs() {
  const box = document.getElementById("logs");
  const data = await api("/api/admin/logs?lines=150");
  box.textContent = data.lines.join("\n") || "No log lines yet.";
  box.scrollTop = box.scrollHeight;
}

function refreshAll() { loadStats(); loadDocs(); loadLogs(); }

// ---------- upload files ----------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");

async function uploadFiles(files) {
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  setStatus(uploadStatus, `Adding ${files.length} file(s)…`);
  try {
    const res = await api("/api/admin/documents/upload", { method: "POST", formData: fd });
    const added = res.added.map(d => `${d.name} (${d.chunks} chunks)`).join(", ");
    const msg = (added ? `Added: ${added}. ` : "") + (res.errors.length ? `Problems: ${res.errors.join(" ")}` : "");
    setStatus(uploadStatus, msg, res.errors.length === 0);
  } catch (err) {
    setStatus(uploadStatus, err.message, false);
  }
  fileInput.value = "";
  refreshAll();
}
fileInput.onchange = () => uploadFiles(fileInput.files);
dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
["dragenter", "dragover"].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev => dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", e => uploadFiles(e.dataTransfer.files));

// ---------- add web page ----------
document.getElementById("url-form").addEventListener("submit", async e => {
  e.preventDefault();
  const url = document.getElementById("url-input").value.trim();
  const status = document.getElementById("url-status");
  const btn = document.getElementById("url-btn");
  btn.disabled = true;
  setStatus(status, "Reading the page…");
  try {
    const d = await api("/api/admin/documents/url", { method: "POST", json: { url } });
    setStatus(status, `Added the page (${d.words.toLocaleString()} words, ${d.chunks} chunks).`);
    document.getElementById("url-input").value = "";
    refreshAll();
  } catch (err) {
    setStatus(status, err.message, false);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("reload-folder").onclick = async () => {
  const res = await api("/api/admin/documents/reload-folder", { method: "POST" });
  setStatus(uploadStatus, `Reloaded ${res.loaded} file(s) from the knowledge_base folder.`);
  refreshAll();
};
document.getElementById("refresh-logs").onclick = loadLogs;

refreshAll();
