// Página da tarefa (/tasks/:id): responsável, prazo, prioridade, labels, checklist e comentários
const TASK_ID = Number(location.pathname.split("/").filter(Boolean).pop());
const ROLE_LABEL = { OWNER: "Dono", EDITOR: "Editor", VIEWER: "Leitor" };
const $ = id => document.getElementById(id);
let data = null, checklist = [], saveTimer = null, dirty = false, toastTimer = null;
const canEdit = () => data && data.role !== "VIEWER";

function notify(m) { const t = $("toast"); t.textContent = m; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3200); }
function setSaveState(text) { $("saveState").textContent = text; }

function fillSelect(select, options, value) {
  select.textContent = "";
  options.forEach(([v, t]) => { const o = document.createElement("option"); o.value = v; o.textContent = t; select.appendChild(o); });
  select.value = value;
}
function renderAll() {
  const t = data.task;
  $("layout").hidden = false;
  $("boardName").textContent = data.board.name;
  $("backLink").href = `/board/${data.board.id}`;
  $("roleBadge").textContent = ROLE_LABEL[data.role]; $("roleBadge").className = `role-badge r-${data.role}`;
  $("accName").textContent = data.me.name; $("avatar").textContent = initials(data.me.name);
  document.title = `${t.title} | Quadro Kanban`;
  $("title").value = t.title; $("desc").value = t.description;
  fillSelect($("column"), data.columns.map(c => [c.id, c.name]), t.column_id);
  fillSelect($("assignee"), [["", "Sem responsável"], ...data.members.map(m => [m.id, m.name])], t.assignee_id || "");
  $("due").value = t.due_date; $("priority").value = t.priority; $("labels").value = t.labels.join(", ");
  checklist = t.checklist.map(i => ({ ...i }));
  renderChecklist(); renderComments();
  const edit = canEdit();
  ["title", "desc", "column", "assignee", "due", "priority", "labels", "checkText"].forEach(id => { $(id).disabled = !edit; });
  $("checkForm").hidden = !edit; $("commentForm").hidden = false; $("viewerNote").hidden = true;
}
function renderChecklist() {
  const ul = $("checklist"); ul.textContent = "";
  checklist.forEach((item, i) => {
    const li = document.createElement("li"); li.className = "check-row" + (item.done ? " done" : "");
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = item.done; cb.disabled = !canEdit();
    cb.setAttribute("aria-label", item.text);
    cb.addEventListener("change", () => { item.done = cb.checked; renderChecklist(); queueSave(); });
    const span = document.createElement("span"); span.textContent = item.text;
    li.append(cb, span);
    if (canEdit()) {
      const del = document.createElement("button"); del.type = "button"; del.className = "icon-btn"; del.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>'; del.setAttribute("aria-label", "Remover item");
      del.addEventListener("click", () => { checklist.splice(i, 1); renderChecklist(); queueSave(); }); li.appendChild(del);
    }
    ul.appendChild(li);
  });
  const done = checklist.filter(i => i.done).length;
  $("checkCount").textContent = checklist.length ? `${done}/${checklist.length}` : "";
  $("progressBar").style.width = checklist.length ? `${Math.round(done / checklist.length * 100)}%` : "0";
}
let shownComments = "";
function renderComments() {
  const key = JSON.stringify(data.comments.map(c => c.id));
  if (key === shownComments) return; shownComments = key;
  const box = $("comments"); box.textContent = "";
  if (!data.comments.length) { const p = document.createElement("div"); p.className = "empty"; p.textContent = "Nenhum comentário ainda."; box.appendChild(p); return; }
  data.comments.forEach(c => {
    const el = document.createElement("div"); el.className = "comment";
    const h = document.createElement("header"); const a = document.createElement("b"); a.textContent = c.author;
    const d = document.createElement("span"); d.textContent = fmtDateTime(c.created_at); h.append(a, d);
    const p = document.createElement("p"); p.textContent = c.text; el.append(h, p); box.appendChild(el);
  });
}

function collect() {
  return {
    title: $("title").value, description: $("desc").value, column_id: Number($("column").value),
    assignee_id: $("assignee").value === "" ? null : Number($("assignee").value),
    due_date: $("due").value, priority: $("priority").value,
    labels: $("labels").value.split(",").map(s => s.trim()).filter(Boolean), checklist
  };
}
function queueSave() {
  if (!canEdit()) return;
  dirty = true; setSaveState("Salvando..."); clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 600);
}
async function save() {
  const body = collect();
  if (!body.title.trim()) { setSaveState("O título não pode ficar vazio"); return; }
  try {
    const res = await api(`/tasks/${TASK_ID}`, { method: "PATCH", body });
    data.task = res.task; dirty = false; document.title = `${res.task.title} | Quadro Kanban`; setSaveState("Alterações salvas");
  } catch (e) { setSaveState("Falha ao salvar"); notify(e.message); }
}
["title", "desc", "column", "assignee", "due", "priority", "labels"].forEach(id => {
  $(id).addEventListener(id === "title" || id === "desc" || id === "labels" ? "input" : "change", queueSave);
});
$("checkForm").addEventListener("submit", e => {
  e.preventDefault(); const text = $("checkText").value.trim(); if (!text) return;
  checklist.push({ text, done: false }); $("checkText").value = ""; renderChecklist(); queueSave();
});
$("commentForm").addEventListener("submit", async e => {
  e.preventDefault(); const text = $("commentText").value.trim(); if (!text) return;
  try {
    const { comment } = await api(`/tasks/${TASK_ID}/comments`, { method: "POST", body: { text } });
    data.comments.push(comment); $("commentText").value = ""; renderComments();
  } catch (err) { notify(err.message); }
});
$("logout").addEventListener("click", doLogout);

async function load() {
  try { data = await api(`/tasks/${TASK_ID}`); renderAll(); }
  catch (e) { $("boardName").textContent = e.message; setTimeout(() => { location.href = "/boards"; }, 1800); }
}
// atualiza comentários (e campos, se ninguém estiver editando) a cada poucos segundos
setInterval(async () => {
  if (!data || document.hidden) return;
  try {
    const fresh = await api(`/tasks/${TASK_ID}`);
    const editing = dirty || document.activeElement.closest(".panel input, .panel textarea, .panel select") && document.activeElement.matches("input,textarea,select");
    if (!editing) { const same = JSON.stringify(fresh.task) === JSON.stringify(data.task); data = fresh; if (!same) renderAll(); else renderComments(); }
    else { data.comments = fresh.comments; renderComments(); }
  } catch (e) { if (e.status === 404 || e.status === 403) location.href = "/boards"; }
}, 5000);
load();
