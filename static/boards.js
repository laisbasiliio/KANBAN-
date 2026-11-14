const ROLE_LABEL = { OWNER: "Dono", EDITOR: "Editor", VIEWER: "Leitor" };
function toast(message) { const t = document.getElementById("toast"); t.textContent = message; t.hidden = false; setTimeout(() => { t.hidden = true; }, 3200); }

const TILE_COLORS = [
  ["#2563eb", "#7c3aed"], ["#0ea5e9", "#2563eb"], ["#0f9d83", "#0ea5e9"], ["#db4777", "#7c3aed"],
  ["#d97706", "#db4777"], ["#7c3aed", "#4f46e5"], ["#16a34a", "#0f9d83"], ["#e11d48", "#d97706"]
];
const SVG = {
  tasks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg>',
  people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M17 5.5a3.5 3.5 0 0 1 0 6.5M18.5 14.4c2 .7 3.5 2.6 3.5 5.6"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/></svg>'
};
function pill(kind, text) {
  const s = document.createElement("span"); s.className = `pill pill-${kind}`;
  s.innerHTML = SVG[kind]; s.append(text); return s;
}
function tile(board, shared) {
  const [c1, c2] = TILE_COLORS[board.id % TILE_COLORS.length];
  const wrap = document.createElement("div"); wrap.className = "tile-wrap";
  wrap.style.setProperty("--tc", c1); wrap.style.setProperty("--tc2", c2);
  const a = document.createElement("a"); a.className = "board-tile"; a.href = `/board/${board.id}`;
  const top = document.createElement("div"); top.className = "tile-top";
  const av = document.createElement("span"); av.className = "tile-avatar"; av.textContent = (board.name.trim()[0] || "?").toUpperCase();
  const badge = document.createElement("span"); badge.className = `role-badge r-${board.role}`; badge.textContent = ROLE_LABEL[board.role];
  top.append(av, badge);
  const body = document.createElement("div"); body.className = "tile-body";
  const h = document.createElement("h3"); h.textContent = board.name;
  const stats = document.createElement("div"); stats.className = "tile-stats";
  stats.append(pill("tasks", `${board.task_count} tarefa(s)`), pill("people", `${board.member_count} membro(s)`));
  body.append(h, stats);
  if (shared) { const by = document.createElement("div"); by.className = "tile-owner"; by.textContent = `Compartilhado por ${board.owner_name}`; body.appendChild(by); }
  a.append(top, body); wrap.appendChild(a);
  if (board.role === "OWNER") {
    const del = document.createElement("button");
    del.type = "button"; del.className = "tile-del"; del.title = "Excluir quadro"; del.setAttribute("aria-label", `Excluir quadro ${board.name}`);
    del.innerHTML = SVG.trash;
    del.addEventListener("click", async () => {
      if (!confirm(`Excluir o quadro “${board.name}”? Todas as tarefas, comentários e acessos serão apagados e isso não pode ser desfeito.`)) return;
      try { await api(`/boards/${board.id}`, { method: "DELETE" }); toast("Quadro excluído."); load(); }
      catch (e) { toast(e.message); }
    });
    wrap.appendChild(del);
  }
  return wrap;
}
function fill(boxId, countId, items, shared, emptyText) {
  const box = document.getElementById(boxId); box.textContent = "";
  document.getElementById(countId).textContent = items.length ? `${items.length}` : "";
  if (!items.length) { const e = document.createElement("div"); e.className = "empty-box"; e.textContent = emptyText; box.style.display = "block"; box.appendChild(e); return; }
  box.style.display = ""; items.forEach(b => box.appendChild(tile(b, shared)));
  if (!shared) {
    const add = document.createElement("button"); add.type = "button"; add.className = "tile-new";
    add.innerHTML = '<span>+</span>Novo quadro';
    add.addEventListener("click", () => { const i = document.getElementById("newBoardName"); i.scrollIntoView({ behavior: "smooth", block: "center" }); i.focus(); });
    box.appendChild(add);
  }
}
async function load() {
  try {
    const [{ user }, lists] = await Promise.all([api("/me"), api("/boards")]);
    document.getElementById("accName").textContent = user.name;
    document.getElementById("avatar").textContent = initials(user.name);
    const all = [...lists.mine, ...lists.shared];
    document.getElementById("stBoards").textContent = all.length;
    document.getElementById("stTasks").textContent = all.reduce((n, b) => n + b.task_count, 0);
    document.getElementById("stShared").textContent = lists.shared.length;
    document.getElementById("stOwner").textContent = lists.mine.length;
    const first = String(user.name || "").trim().split(/\s+/)[0];
    if (first) document.getElementById("greet").textContent = `Olá, ${first}! Crie quadros e acesse os que foram compartilhados com você.`;
    fill("mine", "mineCount", lists.mine, false, "Você ainda não criou nenhum quadro. Use o campo acima para começar.");
    fill("shared", "sharedCount", lists.shared, true, "Nenhum quadro foi compartilhado com você ainda.");
  } catch (e) { toast(e.message); }
}
document.getElementById("newBoardForm").addEventListener("submit", async event => {
  event.preventDefault();
  const input = document.getElementById("newBoardName");
  try { const board = await api("/boards", { method: "POST", body: { name: input.value.trim() } }); location.href = `/board/${board.id}`; }
  catch (e) { toast(e.message); }
});
document.getElementById("logout").addEventListener("click", doLogout);
load();
