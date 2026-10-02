// Shared helpers. The frontend talks to the backend ONLY through these API calls.
// If you host the frontend somewhere else, set API_BASE to the backend address,
// for example "http://127.0.0.1:8000".
const API_BASE = "";

const auth = {
  get token() { return localStorage.getItem("kd_token"); },
  get user() { try { return JSON.parse(localStorage.getItem("kd_user")); } catch { return null; } },
  save(data) {
    localStorage.setItem("kd_token", data.access_token);
    localStorage.setItem("kd_user", JSON.stringify({ username: data.username, role: data.role }));
  },
  clear() { localStorage.removeItem("kd_token"); localStorage.removeItem("kd_user"); },
  logout() { auth.clear(); window.location.href = "index.html"; },
  requireLogin() { if (!auth.token) window.location.href = "index.html"; },
};

async function api(path, { method = "GET", json, form, formData } = {}) {
  const headers = {};
  let body;
  if (auth.token) headers["Authorization"] = "Bearer " + auth.token;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) { body = new URLSearchParams(form); }
  if (formData) { body = formData; }

  let res;
  try {
    res = await fetch(API_BASE + path, { method, headers, body });
  } catch {
    throw new Error("Cannot reach the backend. Is it running?");
  }
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    auth.logout();
    throw new Error("Please log in again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = data.detail || `Request failed (${res.status}).`;
    if (Array.isArray(msg)) msg = msg.map(d => d.msg).join(" ");
    throw new Error(msg);
  }
  return data;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Very small markdown: **bold**, bullet lists, paragraphs.
function renderMarkdown(text) {
  const lines = escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").split("\n");
  let html = "", inList = false;
  for (const raw of lines) {
    const line = raw.trim();
    const item = line.match(/^([-*•]|\d+\.)\s+(.*)$/);
    if (item) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${item[2]}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (line) html += `<p>${line}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html;
}

function fileType(name) {
  if (name.includes("://")) return "WEB";
  const ext = name.split(".").pop();
  return ext ? ext.toUpperCase() : "FILE";
}
