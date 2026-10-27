"""Contas e sessões do servidor central. Nenhuma senha em texto no banco."""

import hashlib
import hmac
import re
import secrets
import time
from http.cookies import SimpleCookie

ROLES = ("admin", "employee")
IDLE_SECONDS = 1800
MAX_SECONDS = 43200


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


def public(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "active": bool(user["active"]),
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
    login = username(data.get("username"))
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
            "INSERT INTO users VALUES(?,?,?,?,?,?,?,?)",
            (
                uid,
                login,
                name.strip(),
                password,
                "admin" if first else role,
                1,
                employee,
                0 if first else 1,
            ),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError("Este login já existe.") from exc
        raise
    audit(con, actor or {"id": uid, "name": name}, "Conta criada", login)
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
        or time.time() - row["touched"] > IDLE_SECONDS
        or time.time() - row["created"] > MAX_SECONDS
    ):
        return None
    if touch:
        con.execute("UPDATE sessions SET touched=? WHERE digest=?", (time.time(), digest))
    return dict(row, digest=digest)


def login(con, data, ip):
    try:
        name = username(data.get("username"))
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
    row = con.execute("SELECT * FROM users WHERE username=?", (name,)).fetchone()
    correct = verify(data.get("password"), row["password"] if row else DUMMY_HASH)
    if not row or not row["active"] or not correct:
        for key in keys:
            con.execute(
                "INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
                (key, now + 900),
            )
        return None, "Login ou senha inválidos."
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
    active, role = data.get("active"), data.get("role")
    if type(active) is not bool or role not in ROLES:
        raise ValueError("Situação ou perfil inválido.")
    if row["id"] == actor["id"] and (not active or role != "admin"):
        raise ValueError("Você não pode desativar ou retirar o próprio acesso de administrador.")
    if row["role"] == "admin" and row["active"] and (not active or role != "admin"):
        count = con.execute(
            "SELECT count(*) FROM users WHERE role='admin' AND active=1"
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
    audit(con, actor, "Conta atualizada", row["username"])


def apply_changes(current, changes):
    """Compare-and-swap por entidade: pedidos diferentes não conflitam."""
    import copy

    if not isinstance(changes, list) or not 1 <= len(changes) <= 1000:
        raise ValueError("Lista de alterações inválida.")
    next_state = copy.deepcopy(current)
    seen = set()
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
            actual = next((row for row in current[key] if row["id"] == cid), None)
        if "before" not in change or actual != change["before"]:
            raise Conflict(
                "Outra pessoa alterou este registro. Seu formulário foi mantido. Copie suas alterações e atualize os dados antes de tentar novamente."
            )
        after = change.get("after")
        if key in ("company", "warningDays"):
            next_state[key] = copy.deepcopy(after)
        else:
            if not isinstance(after, dict) or after.get("id") != cid:
                raise ValueError("Não é permitido excluir registros.")
            rows = next_state[key]
            if actual is None:
                rows.append(copy.deepcopy(after))
            else:
                rows[rows.index(next(r for r in rows if r["id"] == cid))] = copy.deepcopy(after)
    return next_state


class Conflict(ValueError):
    pass
