// Utilitários compartilhados por todas as páginas
async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    method: opts.method || "GET",
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : {},
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    credentials: "same-origin"
  });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (res.status === 401 && !opts.noRedirect) { location.href = "/login"; throw new Error("Sessão expirada."); }
  if (!res.ok) { const err = new Error((data && data.error) || "Erro inesperado."); err.status = res.status; throw err; }
  return data;
}
function initials(name) {
  return String(name || "?").trim().split(/\s+/).slice(0, 2).map(p => p[0]).join("").toUpperCase();
}
function fmtDateTime(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function fmtDay(ymd) {
  if (!ymd) return "";
  const [y, m, d] = ymd.split("-");
  return `${d}/${m}/${y}`;
}
async function doLogout() {
  try { await api("/logout", { method: "POST", body: {}, noRedirect: true }); } catch (_) {}
  location.href = "/login";
}
