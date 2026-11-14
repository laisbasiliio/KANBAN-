// Chat lateral "Pergunte ao projeto" + extra B (auto-classificação de tarefas).
// Todas as chamadas vão para o NOSSO back-end (/api/ai/*); a chave da IA nunca aparece aqui.
(function () {
  const $ = id => document.getElementById(id);
  const panel = $("chatPanel"), log = $("chatLog"), form = $("chatForm"), input = $("chatInput"), send = $("chatSend");
  let busy = false, greeted = false;

  function setOpen(open) {
    panel.hidden = !open;
    document.body.classList.toggle("chat-open", open);
    $("openChat").setAttribute("aria-expanded", String(open));
    if (open) {
      if (!greeted) { addMsg("bot", "Oi! Pergunte sobre o andamento do projeto, por exemplo: o que está travado, o que falta para lançar ou quem tem mais tarefas."); greeted = true; }
      input.focus();
    }
  }
  $("openChat").addEventListener("click", () => setOpen(panel.hidden));
  $("closeChat").addEventListener("click", () => { setOpen(false); $("openChat").focus(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden && !document.querySelector("dialog[open]")) setOpen(false); });

  // renderiza texto da IA com segurança (sem innerHTML): **negrito** e listas com "- " ou "* "
  function renderText(el, text) {
    el.textContent = "";
    const inline = (parent, str) => str.split(/(\*\*[^*]+\*\*)/g).forEach(part => {
      if (/^\*\*[^*]+\*\*$/.test(part)) { const b = document.createElement("b"); b.textContent = part.slice(2, -2); parent.appendChild(b); }
      else if (part) parent.appendChild(document.createTextNode(part));
    });
    let ul = null;
    text.split("\n").forEach(line => {
      const m = line.match(/^\s*[-*•]\s+(.*)$/);
      if (m) { if (!ul) { ul = document.createElement("ul"); el.appendChild(ul); } const li = document.createElement("li"); inline(li, m[1]); ul.appendChild(li); }
      else { ul = null; if (line.trim()) { const p = document.createElement("p"); inline(p, line); el.appendChild(p); } }
    });
  }
  function addMsg(who, text, extraClass) {
    const div = document.createElement("div");
    div.className = `msg msg-${who}` + (extraClass ? " " + extraClass : "");
    if (who === "bot") renderText(div, text); else div.textContent = text;
    log.appendChild(div); log.scrollTop = log.scrollHeight;
    return div;
  }

  async function ask(question) {
    question = question.trim();
    if (!question || busy) return;
    busy = true; send.disabled = true; input.value = "";
    addMsg("user", question);
    const wait = addMsg("bot", "Analisando os cards...", "msg-wait");
    try {
      const data = await api("/ai/chat", { method: "POST", body: { board_id: BOARD_ID, question } });
      wait.classList.remove("msg-wait"); renderText(wait, data.answer);
    } catch (e) {
      wait.classList.remove("msg-wait"); wait.classList.add("msg-error"); wait.textContent = e.message;
    } finally { busy = false; send.disabled = false; log.scrollTop = log.scrollHeight; input.focus(); }
  }
  form.addEventListener("submit", e => { e.preventDefault(); ask(input.value); });
  $("chatSuggestions").querySelectorAll("button").forEach(b => b.addEventListener("click", () => ask(b.textContent)));

  // ---- Extra B: IA sugere Tag e Prioridade a partir do título/descrição ----
  const classify = $("aiClassify"), hint = $("aiHint");
  classify.addEventListener("click", async () => {
    const title = $("title").value.trim();
    if (!title) { hint.textContent = "Digite o título da tarefa primeiro."; hint.className = "ai-hint err"; $("title").focus(); return; }
    classify.disabled = true; hint.className = "ai-hint"; hint.textContent = "Classificando...";
    try {
      const r = await api("/ai/classify", { method: "POST", body: { board_id: BOARD_ID, title, description: $("desc").value.trim() } });
      $("taskLabels").value = r.labels.join(", "); $("taskPriority").value = r.priority;
      hint.textContent = `Sugestão da IA: tag ${r.labels.join(", ")} · prioridade ${r.priority}. Você pode ajustar antes de salvar.`;
    } catch (e) { hint.className = "ai-hint err"; hint.textContent = e.message; }
    finally { classify.disabled = false; }
  });
})();
