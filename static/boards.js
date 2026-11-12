const ROLE_LABEL = { OWNER: "Dono", EDITOR: "Editor", VIEWER: "Leitor" };
function toast(message) { const t = document.getElementById("toast"); t.textContent = message; t.hidden = false; setTimeout(() => { t.hidden = true; }, 3200); }

function tile(board, shared) {
  const a = document.createElement("a");
  a.className = "board-tile"; a.href = `/board/${board.id}`;
  const h = document.createElement("h3"); h.textContent = board.name;
  const meta = document.createElement("div"); meta.className = "tile-meta";
  const left = document.createElement("span");
  left.textContent = `${board.task_count} tarefa(s) · ${board.member_count} membro(s)` + (shared ? ` · de ${board.owner_name}` : "");
  const badge = document.createElement("span"); badge.className = `role-badge r-${board.role}`; badge.textContent = ROLE_LABEL[board.role];
  meta.append(left, badge); a.append(h, meta);
  const wrap = document.createElement("div"); wrap.className = "tile-wrap"; wrap.appendChild(a);
  if (board.role === "OWNER") {
    const del = document.createElement("button");
    del.type = "button"; del.className = "tile-del"; del.title = "Excluir quadro"; del.setAttribute("aria-label", `Excluir quadro ${board.name}`);
    del.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/></svg>';
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
}
async function load() {
  try {
    const [{ user }, lists] = await Promise.all([api("/me"), api("/boards")]);
    document.getElementById("accName").textContent = user.name;
    document.getElementById("avatar").textContent = initials(user.name);
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
