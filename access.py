"""Contas e sessões do servidor central. Nenhuma senha em texto no banco."""

import hashlib
import hmac
import re
import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from http.cookies import SimpleCookie

ROLES = ("admin", "employee", "embroiderer")
IDLE_SECONDS = 1800
MAX_SECONDS = 43200
_mail_batch = ContextVar("trame_mail_batch", default=None)


@contextmanager
def deferred_mail():
    """Collect delivery work per request, never share codes between threads."""
    messages = []
    token = _mail_batch.set(messages)
    try:
        yield messages
    finally:
        _mail_batch.reset(token)


def smtp_settings():
    import os

    host = os.environ.get("TRAME_SMTP_HOST", "").strip()
    sender = os.environ.get("TRAME_SMTP_FROM", "").strip()
    if not host or not sender:
        raise ValueError(
            "Configure a conta de envio de e-mail no servidor antes de cadastrar contas ou recuperar senhas. Consulte docs/RECUPERACAO-EMAIL.md."
        )
    email_address(sender)
    mode = os.environ.get("TRAME_SMTP_SECURITY", "starttls")
    if mode not in ("ssl", "starttls"):
        raise ValueError("Configure SMTP com SSL ou STARTTLS.")
    try:
        port = int(os.environ.get("TRAME_SMTP_PORT", "465" if mode == "ssl" else "587"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Informe uma porta SMTP válida entre 1 e 65535.") from exc
    return host, sender, mode, port


def email_status():
    try:
        smtp_settings()
        return {
            "configured": True,
            "message": "Conta de envio configurada. A conexão será verificada no envio.",
        }
    except ValueError as exc:
        return {"configured": False, "message": str(exc)}


def queue_email(email, code, verification=False):
    messages = _mail_batch.get()
    if messages is None:
        return send_recovery(email, code, verification=verification)
    smtp_settings()  # Fail before commit if configuration is missing/invalid.
    messages.append((email, code, verification))


def schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
      password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
      employee_id TEXT NOT NULL DEFAULT '', must_change INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sessions (
      digest TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL,
      created REAL NOT NULL, touched REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, count INTEGER, until REAL);
    CREATE TABLE IF NOT EXISTS audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, user_id TEXT,
      name TEXT NOT NULL, action TEXT NOT NULL, details TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS access_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)

    columns = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    if "email" not in columns:
        con.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
    if "email_verified" not in columns:
        con.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
    con.execute(
        "CREATE TABLE IF NOT EXISTS email_verifications (user_id TEXT PRIMARY KEY, digest TEXT NOT NULL, expires REAL NOT NULL, sent REAL NOT NULL)"
    )
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email) WHERE email != ''")
    con.execute(
        "CREATE TABLE IF NOT EXISTS password_resets (user_id TEXT PRIMARY KEY, digest TEXT NOT NULL, expires REAL NOT NULL)"
    )


def email_address(value):
    if not isinstance(value, str):
        raise ValueError("Informe um e-mail válido.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Informe um e-mail válido.")
    return value


def public(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email", ""),
        "name": user["name"],
        "role": user["role"],
        "active": bool(user["active"] and user.get("email_verified", 1)),
        "emailVerified": bool(user.get("email_verified", 1)),
        "enabled": bool(user["active"]),
        "employeeId": user["employee_id"],
        "mustChangePassword": bool(user["must_change"]),
    }


def username(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9._-]{3,60}", value):
        raise ValueError(
            "Login: use de 3 a 60 letras sem acentos, números, ponto, traço ou sublinhado."
        )
    return value.lower()


def hash_password(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise ValueError("A senha deve ter entre 12 e 128 caracteres.")
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(
        value.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024
    )
    return "scrypt$" + salt + "$" + result.hex()


def verify(value, hashed):
    if not isinstance(value, str) or len(value) > 128:
        return False
    try:
        _, salt, expected = hashed.split("$")
        result = hashlib.scrypt(
            value.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024
        )
        return hmac.compare_digest(result.hex(), expected)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password("dummy-unusable-password-" + secrets.token_hex(8))


def audit(con, user, action, details=""):
    con.execute(
        "INSERT INTO audit(at,user_id,name,action,details) VALUES(?,?,?,?,?)",
        (time.time(), user.get("id"), user.get("name", "Acesso"), action, details[:2000]),
    )


def create_user(con, data, actor=None, first=False):
    email = email_address(data["email"]) if "email" in data else ""
    login = username(data["username"]) if data.get("username") else email
    if not login:
        raise ValueError("Informe um e-mail para criar a conta.")
    name = data.get("name", "")
    role = data.get("role", "employee")
    employee = data.get("employeeId", "")
    if (
        not isinstance(name, str)
        or not 2 <= len(name.strip()) <= 150
        or role not in ROLES
        or not isinstance(employee, str)
    ):
        raise ValueError("Informe nome e perfil válidos.")
    if employee and con.execute("SELECT 1 FROM users WHERE employee_id=?", (employee,)).fetchone():
        raise ValueError("Este funcionário já possui uma conta.")
    password = hash_password(data.get("password"))
    uid = secrets.token_hex(16)
    try:
        con.execute(
            "INSERT INTO users(id,username,name,password,role,active,employee_id,must_change,email) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                uid,
                login,
                name.strip(),
                password,
                "admin" if first else role,
                1,
                employee,
                0 if first else 1,
                email,
            ),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("Este login já existe.") from exc
        raise
    audit(con, actor or {"id": uid, "name": name}, "Conta criada", login)
    if email:
        con.execute("UPDATE users SET email_verified=0 WHERE id=?", (uid,))
        issue_verification(con, uid, email)
    return uid


def session(con, cookie, touch=False):
    cookies = SimpleCookie()
    try:
        cookies.load(cookie or "")
        token = cookies.get("trame_session")
        token = token.value if token else ""
    except Exception:
        token = ""
    digest = hashlib.sha256(token.encode()).hexdigest()
    con.row_factory = __import__("sqlite3").Row
    row = con.execute(
        """SELECT users.*, sessions.csrf, sessions.created, sessions.touched
        FROM sessions JOIN users ON users.id=sessions.user_id WHERE digest=?""",
        (digest,),
    ).fetchone()
    if (
        not row
        or not row["active"]
        or not row["email_verified"]
        or time.time() - row["touched"] > IDLE_SECONDS
        or time.time() - row["created"] > MAX_SECONDS
    ):
        return None
    if touch:
        con.execute("UPDATE sessions SET touched=? WHERE digest=?", (time.time(), digest))
    return dict(row, digest=digest)


def login(con, data, ip):
    try:
        value = data.get("username", "")
        name = email_address(value) if isinstance(value, str) and "@" in value else username(value)
    except ValueError:
        name = "_invalid"
    now = time.time()
    keys = ["ip:" + ip, "user:" + name]
    con.execute("DELETE FROM attempts WHERE until<?", (now,))
    for key in keys:
        row = con.execute("SELECT count FROM attempts WHERE key=?", (key,)).fetchone()
        if row and row[0] >= (30 if key.startswith("ip:") else 8):
            return None, "Muitas tentativas. Aguarde 15 minutos para tentar novamente."
    con.row_factory = __import__("sqlite3").Row
    row = con.execute("SELECT * FROM users WHERE username=? OR email=?", (name, name)).fetchone()
    correct = verify(data.get("password"), row["password"] if row else DUMMY_HASH)
    if not row or not row["active"] or not correct:
        for key in keys:
            con.execute(
                "INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
                (key, now + 900),
            )
        return None, "Login ou senha inválidos."
    if not row["email_verified"]:
        return None, "Confirme seu e-mail com o código recebido antes de entrar."
    con.execute("DELETE FROM attempts WHERE key=?", ("user:" + name,))
    con.execute(
        "DELETE FROM sessions WHERE touched<? OR created<?", (now - IDLE_SECONDS, now - MAX_SECONDS)
    )
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    con.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (digest, row["id"], csrf, now, now))
    audit(con, dict(row), "Entrou no sistema")
    return (token, dict(row, csrf=csrf)), None


def update_user(con, data, actor):
    con.row_factory = __import__("sqlite3").Row
    row = con.execute("SELECT * FROM users WHERE id=?", (data.get("id"),)).fetchone()
    if not row:
        raise ValueError("Conta não encontrada.")
    if data.get("email"):
        email = email_address(data["email"])
        try:
            if email != row["email"]:
                if (
                    row["role"] == "admin"
                    and row["active"]
                    and row["email_verified"]
                    and con.execute(
                        "SELECT count(*) FROM users WHERE role='admin' AND active=1 AND email_verified=1 AND id!=?",
                        (row["id"],),
                    ).fetchone()[0]
                    == 0
                ):
                    raise ValueError(
                        "Cadastre outro administrador confirmado antes de alterar o e-mail desta conta."
                    )
                con.execute(
                    "UPDATE users SET email=?,email_verified=0 WHERE id=?", (email, row["id"])
                )
                issue_verification(con, row["id"], email)
        except __import__("sqlite3").IntegrityError as exc:
            raise ValueError("Este e-mail já está cadastrado.") from exc
        con.execute("DELETE FROM password_resets WHERE user_id=?", (row["id"],))
    active, role = data.get("active"), data.get("role")
    if type(active) is not bool or role not in ROLES:
        raise ValueError("Situação ou perfil inválido.")
    if row["id"] == actor["id"] and (not active or role != "admin"):
        raise ValueError("Você não pode desativar ou retirar o próprio acesso de administrador.")
    if (
        row["role"] == "admin"
        and row["active"]
        and row["email_verified"]
        and (not active or role != "admin")
    ):
        count = con.execute(
            "SELECT count(*) FROM users WHERE role='admin' AND active=1 AND email_verified=1"
        ).fetchone()[0]
        if count <= 1:
            raise ValueError("Mantenha pelo menos um administrador ativo.")
    con.execute("UPDATE users SET active=?,role=? WHERE id=?", (int(active), role, row["id"]))
    if data.get("password"):
        con.execute(
            "UPDATE users SET password=?,must_change=1 WHERE id=?",
            (hash_password(data["password"]), row["id"]),
        )
    con.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    con.execute("DELETE FROM password_resets WHERE user_id=?", (row["id"],))
    audit(con, actor, "Conta atualizada", row["username"])


def export_account(con, user):
    """Somente o perfil e as ações desta conta; nunca exporta credenciais."""
    con.row_factory = __import__("sqlite3").Row
    history = con.execute(
        "SELECT at,action FROM audit WHERE user_id=? ORDER BY id", (user["id"],)
    ).fetchall()
    return {
        "account": public(user),
        "exportedAt": time.time(),
        "activity": [dict(row) for row in history],
    }


def delete_account(con, user, data):
    if data.get("acknowledged") is not True:
        raise ValueError("Marque a confirmação de ciência para continuar.")
    key = "delete-account:" + user["id"]
    attempt = con.execute("SELECT count,until FROM attempts WHERE key=?", (key,)).fetchone()
    if attempt and attempt[1] > time.time() and attempt[0] >= 5:
        raise ValueError("Muitas tentativas. Aguarde 15 minutos para tentar novamente.")
    if not verify(data.get("currentPassword"), user["password"]):
        if not attempt or attempt[1] <= time.time():
            con.execute("INSERT OR REPLACE INTO attempts VALUES(?,1,?)", (key, time.time() + 900))
        else:
            con.execute("UPDATE attempts SET count=count+1 WHERE key=?", (key,))
        con.commit()
        raise ValueError("Senha atual inválida.")
    if (
        user["role"] == "admin"
        and con.execute(
            "SELECT count(*) FROM users WHERE role='admin' AND active=1 AND email_verified=1 AND id!=?",
            (user["id"],),
        ).fetchone()[0]
        == 0
    ):
        raise ValueError("Cadastre outro administrador ativo antes de excluir sua conta.")
    audit(con, user, "Conta excluída pelo titular")
    for table in ("sessions", "password_resets", "email_verifications"):
        con.execute("DELETE FROM " + table + " WHERE user_id=?", (user["id"],))
    con.execute("DELETE FROM attempts WHERE key IN (?,?)", (key, "user:" + user["username"]))
    con.execute("DELETE FROM users WHERE id=?", (user["id"],))


def visible_state(data):
    import copy

    data = copy.deepcopy(data)
    for key in ("orders", "clients", "employees", "stock"):
        data[key] = [row for row in data.get(key, []) if not row.get("_deleted")]
    for order in data.get("orders", []):
        order["items"] = [item for item in order["items"] if not item.get("_deleted")]
    return data


def preserve_excluded(candidate, old):
    import copy

    for key in ("orders", "clients", "employees", "stock"):
        old_rows = {row["id"]: row for row in old[key]}
        new_rows = {row["id"]: row for row in candidate[key]}
        for rid, prior in old_rows.items():
            if prior.get("_deleted"):
                if rid in new_rows and new_rows[rid] != prior:
                    raise ValueError("Registros excluídos são preservados no histórico.")
                if rid not in new_rows:
                    candidate[key].append(copy.deepcopy(prior))
        for row in candidate[key]:
            prior = old_rows.get(row["id"])
            if row.get("_deleted") and (not prior or row != prior):
                raise ValueError("Use a confirmação de exclusão.")
            if key == "orders" and prior and not prior.get("_deleted"):
                hidden = {i["id"]: i for i in prior["items"] if i.get("_deleted")}
                for item in row["items"]:
                    if item.get("_deleted") and item != hidden.get(item["id"]):
                        raise ValueError("Use a confirmação de exclusão de modelos.")
                present = {i["id"] for i in row["items"]}
                row["items"].extend(
                    copy.deepcopy(i) for iid, i in hidden.items() if iid not in present
                )


def delete_record(con, data, actor, runtime):
    import json

    if data.get("confirmed") is not True:
        raise ValueError("Marque a confirmação de ciência para excluir.")
    scope, rid = data.get("scope"), data.get("id")
    if not isinstance(rid, str) or not rid:
        raise ValueError("Registro inválido.")
    stamp = {"at": time.time(), "by": actor["id"]}
    if scope in ("orders", "clients", "employees", "stock", "items"):
        if scope == "employees" and actor["role"] != "admin":
            raise ValueError("Somente administradores excluem funcionários.")
        revision, payload = con.execute("SELECT revision,payload FROM state WHERE id=1").fetchone()
        if data.get("revision") != revision:
            raise Conflict("Os dados mudaram. Atualize antes de excluir.")
        state = runtime.defaults(json.loads(payload))
        owner = (
            next((o for o in state["orders"] if any(i["id"] == rid for i in o["items"])), None)
            if scope == "items"
            else None
        )
        row = next(
            (
                r
                for r in (owner["items"] if owner else [] if scope == "items" else state[scope])
                if r["id"] == rid
            ),
            None,
        )
        if not row or row.get("_deleted"):
            raise ValueError("Registro não encontrado ou já excluído.")
        if scope in ("orders", "items"):
            order = row if scope == "orders" else owner
            if any(not p.get("voided") for p in order.get("payments", [])):
                raise ValueError(
                    "Anule os recebimentos com motivo antes de excluir este pedido ou modelo."
                )
            item_ids = {i["id"] for i in order["items"]} if scope == "orders" else {rid}
            if any(
                r["itemId"] in item_ids and r["stage"] == "Reservado" for r in state["reservations"]
            ):
                raise ValueError("Libere as reservas deste pedido ou modelo antes de excluir.")
            if scope == "items" and (
                row.get("tasks") or row.get("deliveries") or row.get("stage") != "Aguardando"
            ):
                raise ValueError(
                    "Este modelo já tem produção ou entregas. Exclua o pedido completo para preservar seu histórico."
                )
            if scope == "orders":
                row["archived"] = True
        if scope == "stock" and any(
            r["stockId"] == rid and r["stage"] == "Reservado" for r in state["reservations"]
        ):
            raise ValueError("Libere as reservas do estoque antes de excluir.")
        row["_deleted"] = stamp
        if scope == "items" and runtime.money(owner)["total"] < 0:
            raise ValueError(
                "A exclusão deixaria o pedido com valor negativo. Revise os descontos antes."
            )
        if scope in ("clients", "employees", "stock"):
            row["active"] = False
        con.execute(
            "UPDATE state SET revision=?,payload=? WHERE id=1",
            (revision + 1, json.dumps(state, ensure_ascii=False)),
        )
        label = row.get("name") or row.get("client") or row.get("type") or rid
    elif scope in ("services", "serviceCompanies", "embroideryStock"):
        import services

        if not services.allowed(actor):
            raise ValueError("Área exclusiva do administrador e do perfil Bordador(a).")
        table = {
            "services": "service_jobs",
            "serviceCompanies": "service_companies",
            "embroideryStock": "embroidery_stock",
        }[scope]
        found = con.execute(
            "SELECT revision,payload FROM " + table + " WHERE id=?", (rid,)
        ).fetchone()
        if not found:
            raise ValueError("Registro não encontrado.")
        services.check_revision(found[0], data.get("revision"))
        row = json.loads(found[1])
        if row.get("_deleted"):
            raise ValueError("Registro já excluído.")
        if scope == "services":
            if services.eligible(row) and services.is_closed(
                con, row["technique"], services.period(row)
            ):
                raise ValueError("Reabra o fechamento do mês antes de excluir este serviço.")
            if services.amounts(row)["receivedCents"]:
                raise ValueError("Anule os recebimentos antes de excluir o serviço.")
        row.update(_deleted=stamp, active=False, revision=found[0] + 1)
        con.execute(
            "UPDATE " + table + " SET revision=?,payload=? WHERE id=?",
            (row["revision"], json.dumps(row, ensure_ascii=False), rid),
        )
        label = row.get("name") or row.get("code") or rid
    else:
        raise ValueError("Tipo de registro inválido.")
    audit(con, actor, "Registro excluído", scope + " · " + label)
    return {"ok": True}


def apply_changes(current, changes):
    """Compare-and-swap por entidade: pedidos diferentes não conflitam."""
    import copy

    if not isinstance(changes, list) or not 1 <= len(changes) <= 1000:
        raise ValueError("Lista de alterações inválida.")
    next_state = copy.deepcopy(current)
    seen = set()
    indexes = {}
    for change in changes:
        key = change.get("key")
        if key not in (
            "orders",
            "clients",
            "employees",
            "stock",
            "reservations",
            "company",
            "warningDays",
        ):
            raise ValueError("Área inválida.")
        cid = change.get("id") if key not in ("company", "warningDays") else None
        if (key, cid) in seen:
            raise ValueError("Alteração repetida.")
        seen.add((key, cid))
        if key in ("company", "warningDays"):
            actual = current[key]
        else:
            if not isinstance(cid, str) or not cid:
                raise ValueError("Identificador inválido.")
            if key not in indexes:
                indexes[key] = {row["id"]: pos for pos, row in enumerate(current[key])}
            position = indexes[key].get(cid)
            actual = current[key][position] if position is not None else None
        comparable = copy.deepcopy(actual)
        if key == "orders" and comparable:
            comparable["items"] = [i for i in comparable["items"] if not i.get("_deleted")]
        if isinstance(actual, dict) and actual.get("_deleted"):
            raise ValueError("Este registro foi excluído. Atualize os dados.")
        if "before" not in change or comparable != change["before"]:
            raise Conflict(
                "Outra pessoa alterou este registro. Seu formulário foi mantido. Copie suas alterações e atualize os dados antes de tentar novamente."
            )
        after = change.get("after")
        if isinstance(after, dict):
            after = copy.deepcopy(after)
            if "_deleted" in after and (not actual or after["_deleted"] != actual.get("_deleted")):
                raise ValueError("Use a confirmação de exclusão para excluir registros.")
            if key == "orders" and actual:
                hidden = [i for i in actual["items"] if i.get("_deleted")]
                if any(i.get("_deleted") for i in after.get("items", [])):
                    raise ValueError("Use a confirmação de exclusão para excluir modelos.")
                after["items"] += hidden
        if key in ("company", "warningDays"):
            next_state[key] = copy.deepcopy(after)
        else:
            if not isinstance(after, dict) or after.get("id") != cid:
                raise ValueError("Não é permitido excluir registros.")
            rows = next_state[key]
            if actual is None:
                rows.append(copy.deepcopy(after))
            else:
                rows[position] = copy.deepcopy(after)
    return next_state


class Conflict(ValueError):
    pass


def recovery_limit(con, ip, email):
    now = time.time()
    con.execute("DELETE FROM attempts WHERE until<?", (now,))
    keys = ["recovery-ip:" + ip, "recovery-email:" + email]
    for key in keys:
        row = con.execute("SELECT count FROM attempts WHERE key=?", (key,)).fetchone()
        if row and row[0] >= 5:
            raise ValueError("Muitas tentativas. Aguarde 15 minutos para tentar novamente.")
    for key in keys:
        con.execute(
            "INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
            (key, now + 900),
        )
    con.commit()


@contextmanager
def smtp_connection():
    import os
    import smtplib
    import ssl

    host, sender, mode, port = smtp_settings()
    client = smtplib.SMTP_SSL if mode == "ssl" else smtplib.SMTP
    options = {"context": ssl.create_default_context()} if mode == "ssl" else {}
    try:
        with client(host, port, timeout=15, **options) as smtp:
            if mode == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(
                os.environ.get("TRAME_SMTP_USER", sender), os.environ.get("TRAME_SMTP_PASSWORD", "")
            )
            yield smtp
    except (OSError, smtplib.SMTPException) as exc:
        raise ValueError(
            "Não foi possível enviar o e-mail. Peça ao administrador para conferir a configuração de envio."
        ) from exc


def check_email_connection():
    """Check TLS and credentials without sending mail or changing the database."""
    with smtp_connection() as smtp:
        code, _ = smtp.noop()
        if code != 250:
            raise ValueError("O servidor de e-mail não confirmou a conexão.")


def send_recovery(email, code, verification=False):
    from email.message import EmailMessage

    _, sender, _, _ = smtp_settings()
    msg = EmailMessage()
    msg["Subject"] = (
        "Tramê — confirme seu e-mail" if verification else "Tramê — recuperação de senha"
    )
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        "Seu código para redefinir a senha do Tramê é: "
        + code
        + "\n\nEle vale por 15 minutos e pode ser usado uma vez. Se você não pediu a recuperação, ignore este e-mail."
    )
    if verification:
        msg.set_content(
            "Seu código para ativar a conta do Tramê é: "
            + code
            + "\n\nEle vale por 15 minutos e só pode ser usado uma vez. Abra Confirmar meu e-mail na tela de entrada. Se você não reconhece este cadastro, ignore esta mensagem."
        )
    with smtp_connection() as smtp:
        smtp.send_message(msg)


def issue_verification(con, uid, email):
    code = secrets.token_hex(8).upper()
    queue_email(email, code, verification=True)
    now = time.time()
    con.execute(
        "INSERT OR REPLACE INTO email_verifications VALUES(?,?,?,?)",
        (uid, hashlib.sha256(code.encode()).hexdigest(), now + 900, now),
    )


def confirm_email(con, data, ip, resend=False):
    email = email_address(data.get("email"))
    recovery_limit(con, "verify:" + ip, "verify:" + email)
    con.execute("BEGIN IMMEDIATE")
    con.row_factory = __import__("sqlite3").Row
    row = con.execute(
        "SELECT * FROM users WHERE email=? AND active=1 AND email_verified=0", (email,)
    ).fetchone()
    if resend:
        if row:
            prior = con.execute(
                "SELECT sent FROM email_verifications WHERE user_id=?", (row["id"],)
            ).fetchone()
            if prior and time.time() - prior[0] < 60:
                raise ValueError("Aguarde um minuto antes de reenviar o código.")
            issue_verification(con, row["id"], email)
            con.commit()
        return {
            "ok": True,
            "message": "Se houver um cadastro pendente, enviaremos um novo código para esse e-mail.",
        }
    code = data.get("code", "")
    record = (
        con.execute(
            "SELECT digest,expires FROM email_verifications WHERE user_id=?", (row["id"],)
        ).fetchone()
        if row
        else None
    )
    if (
        not isinstance(code, str)
        or len(code) > 64
        or not record
        or record[1] < time.time()
        or not hmac.compare_digest(
            record[0], hashlib.sha256(code.strip().upper().encode()).hexdigest()
        )
    ):
        raise ValueError("Código inválido ou expirado. Solicite um novo código.")
    con.execute("UPDATE users SET email_verified=1 WHERE id=?", (row["id"],))
    con.execute("DELETE FROM email_verifications WHERE user_id=?", (row["id"],))
    audit(con, dict(row), "E-mail confirmado")
    con.commit()
    return {"ok": True}


def forgot_password(con, data, ip):
    import os

    email = email_address(data.get("email"))
    recovery_limit(con, ip, email)
    if not os.environ.get("TRAME_SMTP_HOST") or not os.environ.get("TRAME_SMTP_FROM"):
        raise ValueError("O envio de e-mail ainda não foi configurado pelo administrador.")
    con.row_factory = __import__("sqlite3").Row
    row = con.execute(
        "SELECT * FROM users WHERE email=? AND active=1 AND email_verified=1", (email,)
    ).fetchone()
    if row:
        code = secrets.token_hex(8).upper()
        queue_email(email, code)
        con.execute(
            "INSERT OR REPLACE INTO password_resets VALUES(?,?,?)",
            (row["id"], hashlib.sha256(code.encode()).hexdigest(), time.time() + 900),
        )
        con.commit()
    return {
        "ok": True,
        "message": "Se houver uma conta ativa com este e-mail, você receberá um código. Confira também a pasta de spam.",
    }


def reset_password(con, data, ip):
    email = email_address(data.get("email"))
    recovery_limit(con, ip, email)
    code = data.get("code", "")
    if not isinstance(code, str) or len(code) > 64:
        raise ValueError("Código inválido ou expirado.")
    con.row_factory = __import__("sqlite3").Row
    row = con.execute(
        "SELECT users.*, password_resets.digest AS reset_digest, password_resets.expires FROM users JOIN password_resets ON users.id=password_resets.user_id WHERE email=? AND active=1",
        (email,),
    ).fetchone()
    if (
        not row
        or row["expires"] < time.time()
        or not hmac.compare_digest(
            row["reset_digest"], hashlib.sha256(code.strip().upper().encode()).hexdigest()
        )
    ):
        raise ValueError("Código inválido ou expirado.")
    password = hash_password(data.get("newPassword"))
    con.execute("UPDATE users SET password=?,must_change=0 WHERE id=?", (password, row["id"]))
    con.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    con.execute("DELETE FROM password_resets WHERE user_id=?", (row["id"],))
    audit(con, dict(row), "Senha recuperada por e-mail")
    con.commit()
    return {"ok": True}
