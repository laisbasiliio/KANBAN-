# Quadro Kanban colaborativo (Flask + SQLite)

Estrutura: `app.py` na raiz e as páginas em `static/`.

    pip install -r requirements.txt
    python app.py        # http://localhost:5000

## Páginas
- /login            login e cadastro
- /boards           "Meus quadros" e "Compartilhados comigo"
- /board/<id>       quadro Kanban (dono, editor e leitor)
- /tasks/<id>       tarefa em outra aba (responsável, prazo, prioridade, labels, checklist, comentários)

## API (JSON, sessão por cookie)
POST /api/register · POST /api/login · POST /api/logout · GET /api/me
GET/POST /api/boards · GET/PATCH/DELETE /api/boards/<id>
POST /api/boards/<id>/members · PATCH/DELETE /api/boards/<id>/members/<user_id>
POST /api/boards/<id>/columns · PATCH/DELETE /api/columns/<id>
POST /api/boards/<id>/tasks · GET/PATCH/DELETE /api/tasks/<id> · POST /api/tasks/<id>/move
GET/POST /api/tasks/<id>/comments · GET /api/boards/<id>/activity

## Permissões (validadas no back-end)
OWNER: tudo, convida, altera papéis, remove acesso, exclui o quadro.
EDITOR: edita colunas, tarefas e comenta.  VIEWER: somente leitura (a API responde 403).

## Deploy
Procfile: `gunicorn app:app`. Defina SECRET_KEY, e COOKIE_SECURE=1 se usar HTTPS.
O banco é um arquivo SQLite (DATABASE_PATH). Em hospedagens com disco efêmero, use um volume persistente.
