// Login e cadastro (usa /api/login e /api/register)
let mode = "login";
const form = document.getElementById("authForm");
const msg = document.getElementById("message");
const el = id => document.getElementById(id);

function showMessage(text, type) { msg.textContent = text; msg.className = "message " + (type || "error"); msg.hidden = !text; }
function setMode(next) {
  mode = next;
  const reg = mode === "register";
  el("nameLabel").hidden = el("nameWrap").hidden = !reg;
  el("heading").textContent = reg ? "Criar sua conta" : "Entrar na sua conta";
  el("sub").textContent = reg ? "Cadastre-se para criar e compartilhar quadros." : "Acesse seus quadros e os que foram compartilhados com você.";
  el("kicker").textContent = reg ? "NOVO CADASTRO" : "ACESSO";
  el("submitBtn").firstChild.textContent = reg ? "Criar conta" : "Entrar";
  el("switchText").textContent = reg ? "Já tem uma conta?" : "Ainda não tem conta?";
  el("switchBtn").textContent = reg ? "Entrar" : "Criar conta";
  el("password").autocomplete = reg ? "new-password" : "current-password";
  showMessage("");
}
el("switchBtn").addEventListener("click", () => setMode(mode === "login" ? "register" : "login"));

form.addEventListener("submit", async event => {
  event.preventDefault();
  const email = el("email").value.trim(), password = el("password").value, name = el("name").value.trim();
  if (!email || !password || (mode === "register" && !name)) return showMessage("Preencha todos os campos.");
  const btn = el("submitBtn"); btn.disabled = true; showMessage("");
  try {
    await api(mode === "register" ? "/register" : "/login", { method: "POST", body: { name, email, password }, noRedirect: true });
    location.href = "/boards";
  } catch (error) {
    showMessage(error.message);
    btn.disabled = false;
  }
});
const togglePw = el("togglePw");
if (togglePw) togglePw.addEventListener("click", () => {
  const show = el("password").type === "password";
  el("password").type = show ? "text" : "password";
  togglePw.textContent = show ? "Ocultar" : "Mostrar";
  togglePw.setAttribute("aria-pressed", String(show));
});
setMode("login");
