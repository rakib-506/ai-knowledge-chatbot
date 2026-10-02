if (auth.token) window.location.href = "chat.html";

let mode = "login";
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const submit = document.getElementById("auth-submit");
const errorBox = document.getElementById("auth-error");

function setMode(m) {
  mode = m;
  tabLogin.setAttribute("aria-selected", m === "login");
  tabRegister.setAttribute("aria-selected", m === "register");
  submit.textContent = m === "login" ? "Sign in" : "Create account";
  document.getElementById("password").autocomplete = m === "login" ? "current-password" : "new-password";
  errorBox.textContent = "";
}
tabLogin.onclick = () => setMode("login");
tabRegister.onclick = () => setMode("register");

document.getElementById("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  if (username.length < 3) { errorBox.textContent = "Username needs at least 3 characters."; return; }
  if (password.length < 6) { errorBox.textContent = "Password needs at least 6 characters."; return; }

  submit.disabled = true;
  errorBox.textContent = "";
  try {
    const data = mode === "login"
      ? await api("/api/auth/login", { method: "POST", form: { username, password } })
      : await api("/api/auth/register", { method: "POST", json: { username, password } });
    auth.save(data);
    window.location.href = "chat.html";
  } catch (err) {
    errorBox.textContent = err.message;
  } finally {
    submit.disabled = false;
  }
});
