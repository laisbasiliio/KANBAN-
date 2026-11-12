"""Quadro Kanban colaborativo - back-end Flask + SQLite.

Rodar localmente:
    pip install -r requirements.txt
    python app.py            ->  http://localhost:5000

Deploy (ex.: Render/Railway):  gunicorn app:app
Variáveis de ambiente opcionais: SECRET_KEY, DATABASE_PATH, PORT
"""
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, g, jsonify, redirect, request, send_from_directory,
                   session)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "kanban.db"))


def load_secret_key():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = DB_PATH + ".secret"
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        key = secrets.token_hex(32)
        try:
            with open(path, "w") as f:
                f.write(key)
        except OSError:
            pass
        return key


app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)

RANK = {"VIEWER": 1, "EDITOR": 2, "OWNER": 3}
PRIORITIES = ("baixa", "media", "alta")
PALETTE = ["#2563eb", "#4f46e5", "#7c3aed", "#0ea5e9", "#0f9d83", "#d97706", "#db4777"]
DEFAULT_COLUMNS = [("A Fazer", PALETTE[0]), ("Em Andamento", PALETTE[1]), ("Concluído", PALETTE[4])]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS boards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board_members(
  board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('OWNER','EDITOR','VIEWER')),
  PRIMARY KEY(board_id, user_id)
);
CREATE TABLE IF NOT EXISTS board_columns(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  column_id INTEGER NOT NULL REFERENCES board_columns(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0,
  assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  due_date TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'media',
  labels TEXT NOT NULL DEFAULT '[]',
  checklist TEXT NOT NULL DEFAULT '[]',
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_board ON tasks(board_id);
CREATE INDEX IF NOT EXISTS idx_comments_task ON comments(task_id);
CREATE INDEX IF NOT EXISTS idx_activity_board ON activity(board_id);
"""


# ----------------------------------------------------------------- utilidades
def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


class ApiError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.message, self.code = message, code


@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify(error=e.message), e.code


@app.errorhandler(404)
def handle_404(_e):
    if request.path.startswith("/api/"):
        return jsonify(error="Recurso não encontrado."), 404
    return redirect("/boards")


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        uid = session.get("uid")
        user = db().execute("SELECT id, name, email FROM users WHERE id=?", (uid,)).fetchone() if uid else None
        if not user:
            session.clear()
            raise ApiError("Faça login para continuar.", 401)
        g.user = dict(user)
        return fn(*args, **kwargs)
    return wrapper


def board_role(board_id, minimum="VIEWER"):
    """Valida no back-end o papel do usuário no quadro."""
    row = db().execute("SELECT role FROM board_members WHERE board_id=? AND user_id=?",
                       (board_id, g.user["id"])).fetchone()
    if not row:
        raise ApiError("Quadro não encontrado.", 404)
    if RANK[row["role"]] < RANK[minimum]:
        raise ApiError("Seu papel neste quadro não permite essa ação.", 403)
    return row["role"]


def log(board_id, text):
    db().execute("INSERT INTO activity(board_id,user_id,text,created_at) VALUES(?,?,?,?)",
                 (board_id, g.user["id"], text, now()))


def touch_user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


# --------------------------------------------------------------------- páginas
def page(name):
    return send_from_directory(app.static_folder, name)


def logged():
    return bool(session.get("uid"))


@app.route("/")
def home():
    return redirect("/boards" if logged() else "/login")


@app.route("/login")
def login_page():
    return redirect("/boards") if logged() else page("login.html")


@app.route("/boards")
def boards_page():
    return page("boards.html") if logged() else redirect("/login")


@app.route("/board/<int:board_id>")
def board_page(board_id):
    return page("index.html") if logged() else redirect("/login")


@app.route("/tasks/<int:task_id>")
def task_page(task_id):
    return page("task.html") if logged() else redirect("/login")


# ------------------------------------------------------------------------ auth
@app.post("/api/register")
def register():
    data = body()
    name = str(data.get("name", "")).strip()[:60]
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if len(name) < 2:
        raise ApiError("Informe seu nome.")
    if not EMAIL_RE.match(email):
        raise ApiError("Informe um e-mail válido.")
    if len(password) < 6:
        raise ApiError("A senha precisa ter pelo menos 6 caracteres.")
    if db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise ApiError("Já existe uma conta com esse e-mail.", 409)
    cur = db().execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                       (name, email, generate_password_hash(password), now()))
    db().commit()
    session.clear()
    session.permanent = True
    session["uid"] = cur.lastrowid
    return jsonify(user={"id": cur.lastrowid, "name": name, "email": email}), 201


@app.post("/api/login")
def login():
    data = body()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        raise ApiError("E-mail ou senha incorretos.", 401)
    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    return jsonify(user=touch_user(user))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@login_required
def me():
    return jsonify(user=g.user)


@app.get("/api/health")
def health():
    return jsonify(ok=True)


# ---------------------------------------------------------------------- quadros
def members_of(board_id):
    rows = db().execute(
        "SELECT u.id, u.name, u.email, m.role FROM board_members m JOIN users u ON u.id=m.user_id "
        "WHERE m.board_id=? ORDER BY CASE m.role WHEN 'OWNER' THEN 0 WHEN 'EDITOR' THEN 1 ELSE 2 END, u.name",
        (board_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/boards")
@login_required
def list_boards():
    rows = db().execute(
        "SELECT b.id, b.name, b.owner_id, m.role, o.name AS owner_name, "
        "(SELECT COUNT(*) FROM board_members x WHERE x.board_id=b.id) AS member_count, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.board_id=b.id) AS task_count "
        "FROM boards b JOIN board_members m ON m.board_id=b.id AND m.user_id=? "
        "JOIN users o ON o.id=b.owner_id ORDER BY b.id DESC", (g.user["id"],)).fetchall()
    items = [dict(r) for r in rows]
    return jsonify(mine=[b for b in items if b["role"] == "OWNER"],
                   shared=[b for b in items if b["role"] != "OWNER"])


@app.post("/api/boards")
@login_required
def create_board():
    name = str(body().get("name", "")).strip()[:60] or "Meu projeto"
    cur = db().execute("INSERT INTO boards(name,owner_id,created_at) VALUES(?,?,?)", (name, g.user["id"], now()))
    bid = cur.lastrowid
    db().execute("INSERT INTO board_members(board_id,user_id,role) VALUES(?,?,'OWNER')", (bid, g.user["id"]))
    for i, (cname, color) in enumerate(DEFAULT_COLUMNS):
        db().execute("INSERT INTO board_columns(board_id,name,color,position) VALUES(?,?,?,?)", (bid, cname, color, i))
    log(bid, f"criou o quadro “{name}”")
    db().commit()
    return jsonify(id=bid, name=name), 201


def task_select(where, params):
    sql = ("SELECT t.*, u.name AS assignee_name, "
           "(SELECT COUNT(*) FROM comments c WHERE c.task_id=t.id) AS comment_count, "
           "(SELECT c.text FROM comments c WHERE c.task_id=t.id ORDER BY c.id DESC LIMIT 1) AS lc_text, "
           "(SELECT uc.name FROM comments c JOIN users uc ON uc.id=c.user_id WHERE c.task_id=t.id ORDER BY c.id DESC LIMIT 1) AS lc_author "
           "FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id " + where)
    return db().execute(sql, params).fetchall()


def task_dict(row):
    d = dict(row)
    d["labels"] = json.loads(d["labels"] or "[]")
    d["checklist"] = json.loads(d["checklist"] or "[]")
    text, author = d.pop("lc_text", None), d.pop("lc_author", None)
    d["last_comment"] = {"author": author, "text": text} if text else None
    return d


@app.get("/api/boards/<int:board_id>")
@login_required
def get_board(board_id):
    role = board_role(board_id)
    board = db().execute("SELECT id, name, owner_id FROM boards WHERE id=?", (board_id,)).fetchone()
    cols = db().execute("SELECT id, name, color, position FROM board_columns WHERE board_id=? ORDER BY position, id",
                        (board_id,)).fetchall()
    tasks = task_select("WHERE t.board_id=? ORDER BY t.position, t.id", (board_id,))
    return jsonify(board=dict(board), role=role, me=g.user, members=members_of(board_id),
                   columns=[dict(c) for c in cols], tasks=[task_dict(t) for t in tasks])


@app.patch("/api/boards/<int:board_id>")
@login_required
def rename_board(board_id):
    board_role(board_id, "EDITOR")
    name = str(body().get("name", "")).strip()[:60]
    if not name:
        raise ApiError("Informe o nome do projeto.")
    db().execute("UPDATE boards SET name=? WHERE id=?", (name, board_id))
    db().commit()
    return jsonify(ok=True)


@app.delete("/api/boards/<int:board_id>")
@login_required
def delete_board(board_id):
    board_role(board_id, "OWNER")
    db().execute("DELETE FROM boards WHERE id=?", (board_id,))
    db().commit()
    return jsonify(ok=True)


@app.get("/api/boards/<int:board_id>/activity")
@login_required
def board_activity(board_id):
    board_role(board_id)
    rows = db().execute(
        "SELECT a.id, a.text, a.created_at, u.name AS user_name FROM activity a "
        "LEFT JOIN users u ON u.id=a.user_id WHERE a.board_id=? ORDER BY a.id DESC LIMIT 60", (board_id,)).fetchall()
    return jsonify(items=[dict(r) for r in rows])


# --------------------------------------------------------------------- membros
@app.post("/api/boards/<int:board_id>/members")
@login_required
def add_member(board_id):
    board_role(board_id, "OWNER")
    data = body()
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "EDITOR")).upper()
    if role not in ("EDITOR", "VIEWER"):
        raise ApiError("Papel inválido. Use EDITOR ou VIEWER.")
    user = db().execute("SELECT id, name, email FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        raise ApiError("Nenhum usuário com esse e-mail. Peça para a pessoa criar uma conta primeiro.", 404)
    if db().execute("SELECT 1 FROM board_members WHERE board_id=? AND user_id=?", (board_id, user["id"])).fetchone():
        raise ApiError("Essa pessoa já participa do quadro.", 409)
    db().execute("INSERT INTO board_members(board_id,user_id,role) VALUES(?,?,?)", (board_id, user["id"], role))
    log(board_id, f"convidou {user['name']} como {'editor' if role == 'EDITOR' else 'leitor'}")
    db().commit()
    return jsonify(members=members_of(board_id)), 201


@app.patch("/api/boards/<int:board_id>/members/<int:user_id>")
@login_required
def change_member(board_id, user_id):
    board_role(board_id, "OWNER")
    role = str(body().get("role", "")).upper()
    if role not in ("EDITOR", "VIEWER"):
        raise ApiError("Papel inválido.")
    row = db().execute("SELECT role FROM board_members WHERE board_id=? AND user_id=?", (board_id, user_id)).fetchone()
    if not row:
        raise ApiError("Membro não encontrado.", 404)
    if row["role"] == "OWNER":
        raise ApiError("O papel do dono não pode ser alterado.")
    db().execute("UPDATE board_members SET role=? WHERE board_id=? AND user_id=?", (role, board_id, user_id))
    db().commit()
    return jsonify(members=members_of(board_id))


@app.delete("/api/boards/<int:board_id>/members/<int:user_id>")
@login_required
def remove_member(board_id, user_id):
    role = board_role(board_id)
    if role != "OWNER" and user_id != g.user["id"]:
        raise ApiError("Apenas o dono pode remover o acesso de outras pessoas.", 403)
    row = db().execute("SELECT role FROM board_members WHERE board_id=? AND user_id=?", (board_id, user_id)).fetchone()
    if not row:
        raise ApiError("Membro não encontrado.", 404)
    if row["role"] == "OWNER":
        raise ApiError("O dono não pode ser removido do próprio quadro.")
    db().execute("DELETE FROM board_members WHERE board_id=? AND user_id=?", (board_id, user_id))
    db().execute("UPDATE tasks SET assignee_id=NULL WHERE board_id=? AND assignee_id=?", (board_id, user_id))
    log(board_id, "removeu um membro do quadro" if user_id != g.user["id"] else "saiu do quadro")
    db().commit()
    return jsonify(ok=True)


# ----------------------------------------------------------------------- colunas
def clean_color(value, fallback):
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


@app.post("/api/boards/<int:board_id>/columns")
@login_required
def create_column(board_id):
    board_role(board_id, "EDITOR")
    data = body()
    name = str(data.get("name", "")).strip()[:30]
    if not name:
        raise ApiError("Informe o nome da coluna.")
    pos = db().execute("SELECT COALESCE(MAX(position),-1)+1 FROM board_columns WHERE board_id=?", (board_id,)).fetchone()[0]
    color = clean_color(data.get("color"), PALETTE[pos % len(PALETTE)])
    cur = db().execute("INSERT INTO board_columns(board_id,name,color,position) VALUES(?,?,?,?)",
                       (board_id, name, color, pos))
    log(board_id, f"criou a coluna “{name}”")
    db().commit()
    return jsonify(id=cur.lastrowid), 201


def get_column(column_id, minimum):
    col = db().execute("SELECT * FROM board_columns WHERE id=?", (column_id,)).fetchone()
    if not col:
        raise ApiError("Coluna não encontrada.", 404)
    board_role(col["board_id"], minimum)
    return col


@app.patch("/api/columns/<int:column_id>")
@login_required
def update_column(column_id):
    col = get_column(column_id, "EDITOR")
    data = body()
    name = str(data.get("name", col["name"])).strip()[:30] or col["name"]
    color = clean_color(data.get("color"), col["color"])
    db().execute("UPDATE board_columns SET name=?, color=? WHERE id=?", (name, color, column_id))
    db().commit()
    return jsonify(ok=True)


@app.delete("/api/columns/<int:column_id>")
@login_required
def delete_column(column_id):
    col = get_column(column_id, "EDITOR")
    total = db().execute("SELECT COUNT(*) FROM board_columns WHERE board_id=?", (col["board_id"],)).fetchone()[0]
    if total <= 1:
        raise ApiError("O quadro precisa ter pelo menos uma coluna.")
    db().execute("DELETE FROM board_columns WHERE id=?", (column_id,))
    log(col["board_id"], f"excluiu a coluna “{col['name']}”")
    db().commit()
    return jsonify(ok=True)


# ----------------------------------------------------------------------- tarefas
def clean_fields(data, board_id):
    out = {}
    if "title" in data:
        title = str(data["title"] or "").strip()
        if not title:
            raise ApiError("Informe um título para a tarefa.")
        out["title"] = title[:80]
    if "description" in data:
        out["description"] = str(data["description"] or "").strip()[:400]
    if "column_id" in data:
        col = db().execute("SELECT id FROM board_columns WHERE id=? AND board_id=?",
                           (data["column_id"], board_id)).fetchone()
        if not col:
            raise ApiError("Coluna inválida.")
        out["column_id"] = col["id"]
    if "assignee_id" in data:
        a = data["assignee_id"]
        if a in (None, ""):
            out["assignee_id"] = None
        else:
            m = db().execute("SELECT user_id FROM board_members WHERE board_id=? AND user_id=?",
                             (board_id, a)).fetchone()
            if not m:
                raise ApiError("O responsável precisa ser membro do quadro.")
            out["assignee_id"] = m["user_id"]
    if "due_date" in data:
        v = str(data["due_date"] or "").strip()
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ApiError("Prazo inválido.")
        out["due_date"] = v
    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            raise ApiError("Prioridade inválida. Use baixa, media ou alta.")
        out["priority"] = data["priority"]
    if "labels" in data:
        raw = data["labels"] if isinstance(data["labels"], list) else []
        labels = []
        for x in raw:
            s = str(x).strip()[:20]
            if s and s not in labels:
                labels.append(s)
        out["labels"] = json.dumps(labels[:10], ensure_ascii=False)
    if "checklist" in data:
        raw = data["checklist"] if isinstance(data["checklist"], list) else []
        items = []
        for i in raw:
            if isinstance(i, dict) and str(i.get("text", "")).strip():
                items.append({"text": str(i["text"]).strip()[:120], "done": bool(i.get("done"))})
        out["checklist"] = json.dumps(items[:50], ensure_ascii=False)
    return out


def next_position(column_id):
    return db().execute("SELECT COALESCE(MAX(position),-1)+1 FROM tasks WHERE column_id=?", (column_id,)).fetchone()[0]


@app.post("/api/boards/<int:board_id>/tasks")
@login_required
def create_task(board_id):
    board_role(board_id, "EDITOR")
    data = body()
    if "column_id" not in data:
        first = db().execute("SELECT id FROM board_columns WHERE board_id=? ORDER BY position LIMIT 1",
                             (board_id,)).fetchone()
        data["column_id"] = first["id"]
    fields = clean_fields(data, board_id)
    if "title" not in fields:
        raise ApiError("Informe um título para a tarefa.")
    ts = now()
    cur = db().execute(
        "INSERT INTO tasks(board_id,column_id,title,description,position,assignee_id,due_date,priority,labels,checklist,"
        "created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (board_id, fields["column_id"], fields["title"], fields.get("description", ""),
         next_position(fields["column_id"]), fields.get("assignee_id"), fields.get("due_date", ""),
         fields.get("priority", "media"), fields.get("labels", "[]"), fields.get("checklist", "[]"),
         g.user["id"], ts, ts))
    log(board_id, f"criou a tarefa “{fields['title']}”")
    db().commit()
    return jsonify(id=cur.lastrowid), 201


def get_task_row(task_id, minimum):
    row = db().execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise ApiError("Tarefa não encontrada.", 404)
    return row, board_role(row["board_id"], minimum)


def comments_of(task_id):
    rows = db().execute(
        "SELECT c.id, c.text, c.created_at, c.user_id, u.name AS author FROM comments c "
        "JOIN users u ON u.id=c.user_id WHERE c.task_id=? ORDER BY c.id", (task_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    row, role = get_task_row(task_id, "VIEWER")
    bid = row["board_id"]
    board = db().execute("SELECT id, name FROM boards WHERE id=?", (bid,)).fetchone()
    cols = db().execute("SELECT id, name, color FROM board_columns WHERE board_id=? ORDER BY position, id", (bid,)).fetchall()
    task = task_dict(task_select("WHERE t.id=?", (task_id,))[0])
    return jsonify(task=task, board=dict(board), role=role, me=g.user, members=members_of(bid),
                   columns=[dict(c) for c in cols], comments=comments_of(task_id))


@app.patch("/api/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    row, _ = get_task_row(task_id, "EDITOR")
    fields = clean_fields(body(), row["board_id"])
    if "column_id" in fields and fields["column_id"] != row["column_id"]:
        fields["position"] = next_position(fields["column_id"])
    if fields:
        fields["updated_at"] = now()
        sets = ", ".join(f"{k}=?" for k in fields)  # chaves vêm de lista fixa (clean_fields)
        db().execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), task_id))
        if "column_id" in fields:
            col = db().execute("SELECT name FROM board_columns WHERE id=?", (fields["column_id"],)).fetchone()
            log(row["board_id"], f"moveu “{row['title']}” para {col['name']}")
        db().commit()
    return jsonify(task=task_dict(task_select("WHERE t.id=?", (task_id,))[0]))


@app.post("/api/tasks/<int:task_id>/move")
@login_required
def move_task(task_id):
    row, _ = get_task_row(task_id, "EDITOR")
    data = body()
    col = db().execute("SELECT id, name FROM board_columns WHERE id=? AND board_id=?",
                       (data.get("column_id"), row["board_id"])).fetchone()
    if not col:
        raise ApiError("Coluna inválida.")
    ids = [r["id"] for r in db().execute(
        "SELECT id FROM tasks WHERE column_id=? AND id<>? ORDER BY position, id", (col["id"], task_id))]
    try:
        index = int(data.get("index", len(ids)))
    except (TypeError, ValueError):
        index = len(ids)
    index = max(0, min(index, len(ids)))
    ids.insert(index, task_id)
    db().execute("UPDATE tasks SET column_id=?, updated_at=? WHERE id=?", (col["id"], now(), task_id))
    for pos, tid in enumerate(ids):
        db().execute("UPDATE tasks SET position=? WHERE id=?", (pos, tid))
    if col["id"] != row["column_id"]:
        log(row["board_id"], f"moveu “{row['title']}” para {col['name']}")
    db().commit()
    return jsonify(ok=True)


@app.delete("/api/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    row, _ = get_task_row(task_id, "EDITOR")
    db().execute("DELETE FROM tasks WHERE id=?", (task_id,))
    log(row["board_id"], f"excluiu a tarefa “{row['title']}”")
    db().commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ comentários
@app.get("/api/tasks/<int:task_id>/comments")
@login_required
def list_comments(task_id):
    get_task_row(task_id, "VIEWER")
    return jsonify(comments=comments_of(task_id))


@app.post("/api/tasks/<int:task_id>/comments")
@login_required
def add_comment(task_id):
    # qualquer integrante do quadro (inclusive leitor) pode comentar; comentar não altera a tarefa
    row, _ = get_task_row(task_id, "VIEWER")
    text = str(body().get("text", "")).strip()[:1000]
    if not text:
        raise ApiError("Escreva um comentário.")
    ts = now()
    cur = db().execute("INSERT INTO comments(task_id,user_id,text,created_at) VALUES(?,?,?,?)",
                       (task_id, g.user["id"], text, ts))
    log(row["board_id"], f"comentou em “{row['title']}”")
    db().commit()
    return jsonify(comment={"id": cur.lastrowid, "text": text, "created_at": ts,
                            "user_id": g.user["id"], "author": g.user["name"]}), 201


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
