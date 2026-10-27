"""HTTP autenticado para um servidor central da rede interna."""

import hmac
import hashlib
import ipaddress
import json
import os
import secrets
import ssl
from contextlib import closing
from urllib.parse import urlsplit, quote
import access
import cnpj
import operations


def configuration(home):
    if os.environ.get("TRAME_LOCAL_ONLY") == "1":
        return {
            "bind": "127.0.0.1",
            "port": int(os.environ.get("RADAR_PORT", "18743")),
            "public_url": "",
            "cert": "",
            "key": "",
        }
    path = home / "rede.json"
    data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    return {
        "bind": os.environ.get("RADAR_BIND", data.get("bind", "127.0.0.1")),
        "port": int(os.environ.get("RADAR_PORT", data.get("port", 18743))),
        "public_url": os.environ.get("RADAR_PUBLIC_URL", data.get("public_url", "")).rstrip("/"),
        "cert": os.environ.get("RADAR_CERT", data.get("cert", "")),
        "key": os.environ.get("RADAR_KEY", data.get("key", "")),
    }


def validate_configuration(config):
    local = config["bind"] in ("127.0.0.1", "::1", "localhost")
    url = urlsplit(config["public_url"])
    tls = bool(config["cert"] and config["key"])
    if bool(config["cert"]) != bool(config["key"]):
        raise ValueError("Informe certificado e chave privada juntos.")
    if not local and (not tls or url.scheme != "https" or not url.hostname):
        raise ValueError(
            "Acesso pela rede exige HTTPS: configure public_url, cert e key em rede.json."
        )
    if config["public_url"] and (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username
        or url.password
        or url.path
        or url.query
        or url.fragment
    ):
        raise ValueError(
            "public_url precisa ser uma origem, como https://trame.empresa.local:18743, sem caminho."
        )
    if config["public_url"] and (url.scheme == "https") != tls:
        raise ValueError("O protocolo do endereço deve corresponder ao certificado configurado.")
    return tls


def bootstrap(runtime):
    with closing(runtime.connect()) as con:
        con.execute("PRAGMA journal_mode=WAL")
        if con.execute("SELECT count(*) FROM users").fetchone()[0]:
            return
        token_path = runtime.DB.parent / "chave-primeiro-acesso.txt"
        row = con.execute("SELECT value FROM access_meta WHERE key='setup'").fetchone()
        if not row:
            token = secrets.token_urlsafe(32)
            con.execute("INSERT INTO access_meta VALUES('setup',?)", (token,))
            con.commit()
        else:
            token = row[0]
        token_path.write_text(token, encoding="utf-8")
    print(
        "Primeiro acesso: abra o Tramê NESTE servidor e use a chave de " + str(token_path),
        flush=True,
    )


def backup(runtime):
    from datetime import date

    folder = runtime.DB.parent / "backups-rede"
    folder.mkdir(exist_ok=True)
    target = folder / ("trame-" + date.today().isoformat() + ".sqlite3")
    if target.exists():
        return
    import sqlite3

    temporary = target.with_suffix(".tmp")
    with closing(runtime.connect()) as src, closing(sqlite3.connect(temporary)) as dst:
        src.backup(dst)
    temporary.replace(target)


class AuthenticatedHandler:
    def authority(self):
        # Host verificado também no GET, contra DNS rebinding. Não confiar em X-Forwarded-*.
        config = self.runtime.CONFIG
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        if config["public_url"]:
            allowed.add(urlsplit(config["public_url"]).netloc.lower())
        host = self.headers.get("Host", "").lower()
        if host not in allowed:
            return None
        tls = isinstance(self.connection, ssl.SSLSocket)
        return ("https" if tls else "http") + "://" + host

    def reply(self, status, value, mime="application/json; charset=utf-8", headers=None):
        body = (
            json.dumps(value, ensure_ascii=False).encode()
            if not isinstance(value, bytes)
            else value
        )
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.authority():
            return self.reply(403, {"error": "Endereço do servidor não autorizado."})
        path = urlsplit(self.path).path
        if path == "/health":
            instance = hashlib.sha256(
                str(self.runtime.DB.resolve()).casefold().encode("utf-8")
            ).hexdigest()
            return self.reply(
                200,
                {
                    "status": "ok",
                    "app": "radar-pedidos",
                    "version": 5,
                    "authentication": True,
                    "instance": instance,
                },
            )
        assets = {
            "/theme.css": ("theme.css", "text/css"),
            "/login": ("login.html", "text/html"),
            "/login.js": ("login.js", "text/javascript"),
            "/compat.js": ("compat.js", "text/javascript"),
            "/access.js": ("access.js", "text/javascript"),
            "/access.css": ("access.css", "text/css"),
        }
        if path in assets:
            name, mime = assets[path]
            return self.reply(
                200, (self.runtime.ROOT / "web" / name).read_bytes(), mime + "; charset=utf-8"
            )
        if path in ("/style.css", "/trame.svg", "/trame.ico", "/trame.png"):
            return self.get_business()
        with closing(self.runtime.connect()) as con:
            user = access.session(con, self.headers.get("Cookie"))
            con.commit()
            if path == "/api/session":
                setup = not con.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                return self.reply(
                    200,
                    {
                        "user": access.public(user) if user else None,
                        "csrf": user["csrf"] if user else None,
                        "setupNeeded": setup,
                        "demonstration": os.environ.get("TRAME_DEMO") == "1",
                        "serverUrl": self.runtime.CONFIG["public_url"] or self.authority(),
                    },
                )
            if not user:
                return (
                    self.reply(401, {"error": "Entre com seu login para continuar."})
                    if path.startswith("/api/")
                    else self.reply(
                        303, b"", headers={"Location": "/login?next=" + quote(self.path, safe="")}
                    )
                )
            if user["must_change"]:
                return (
                    self.reply(403, {"error": "Troque sua senha temporária antes de continuar."})
                    if path.startswith("/api/")
                    else self.reply(303, b"", headers={"Location": "/login?change=1"})
                )
            if path == "/api/revision":
                return self.reply(
                    200,
                    {
                        "revision": con.execute("SELECT revision FROM state WHERE id=1").fetchone()[
                            0
                        ]
                    },
                )
            if path in ("/api/users", "/api/audit"):
                if user["role"] != "admin":
                    return self.reply(403, {"error": "Acesso exclusivo de administradores."})
                con.row_factory = __import__("sqlite3").Row
                rows = (
                    con.execute("SELECT * FROM users ORDER BY name").fetchall()
                    if path == "/api/users"
                    else con.execute(
                        "SELECT id,at,name,action,details FROM audit ORDER BY id DESC LIMIT 100"
                    ).fetchall()
                )
                return self.reply(
                    200,
                    [
                        access.public(dict(row)) if path == "/api/users" else dict(row)
                        for row in rows
                    ],
                )
        return self.get_business()

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        limit = 120000000 if self.path in ("/api/state", "/api/changes") else 16384
        if not 0 < length <= limit or self.headers.get_content_type() != "application/json":
            raise ValueError("Envie JSON dentro do limite permitido.")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Dados inválidos.")
        return data

    def session_cookie(self, token, clear=False):
        secure = "; Secure" if isinstance(self.connection, ssl.SSLSocket) else ""
        return (
            f"trame_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else access.MAX_SECONDS}"
            + secure
        )

    def company_lookup(self, data, *, client=False):
        with closing(self.runtime.connect()) as con:
            user = access.session(con, self.headers.get("Cookie"))
            if not user:
                return self.reply(401, {"error": "Entre com seu login para continuar."})
            if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), user["csrf"]):
                return self.reply(403, {"error": "Atualize a sessão antes de continuar."})
            if user["must_change"]:
                return self.reply(403, {"error": "Troque sua senha temporária antes de continuar."})
            if not client and user["role"] != "admin":
                return self.reply(
                    403,
                    {
                        "error": "Somente administradores com a senha atualizada consultam os dados da empresa."
                    },
                )
        # A consulta externa não segura o bloqueio de escrita dos pedidos.
        try:
            result = cnpj.lookup(data.get("cnpj"))
        except cnpj.LookupError as exc:
            return self.reply(exc.status, {"error": str(exc)})
        return self.reply(200, result)

    def do_POST(self):
        origin = self.authority()
        if not origin or self.headers.get("Origin") != origin:
            # No Windows, fechar com um corpo pendente pode descartar a resposta 403.
            # Drene apenas corpos pequenos; requisições grandes continuam recusadas.
            self.close_connection = True
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                length = 0
            if 0 < length <= 16384:
                try:
                    self.rfile.read(length)
                except (OSError, TimeoutError):
                    pass
            return self.reply(403, {"error": "Origem recusada."})
        try:
            data = self.read_json()
            if self.path == "/api/company/cnpj":
                return self.company_lookup(data)
            if self.path == "/api/clients/cnpj":
                return self.company_lookup(data, client=True)
            with self.runtime.LOCK, closing(self.runtime.connect()) as con:
                con.execute("BEGIN IMMEDIATE")
                if self.path == "/api/setup":
                    local = (
                        ipaddress.ip_address(self.client_address[0]).is_loopback
                        or self.client_address[0] == self.server.server_address[0]
                    )
                    token = con.execute(
                        "SELECT value FROM access_meta WHERE key='setup'"
                    ).fetchone()
                    if (
                        not local
                        or con.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                        or not token
                        or not hmac.compare_digest(str(data.get("token", "")), token[0])
                    ):
                        return self.reply(
                            403,
                            {
                                "error": "Configuração inicial recusada. Use a chave no computador servidor."
                            },
                        )
                    access.create_user(con, data, first=True)
                    con.execute("DELETE FROM access_meta WHERE key='setup'")
                    con.commit()
                    (self.runtime.DB.parent / "chave-primeiro-acesso.txt").unlink(missing_ok=True)
                    return self.reply(200, {"ok": True})
                if self.path == "/api/login":
                    result, error = access.login(con, data, self.client_address[0])
                    con.commit()
                    if error:
                        return self.reply(
                            429 if error.startswith("Muitas") else 401, {"error": error}
                        )
                    token, user = result
                    return self.reply(
                        200,
                        {"user": access.public(user), "csrf": user["csrf"]},
                        headers={"Set-Cookie": self.session_cookie(token)},
                    )
                user = access.session(con, self.headers.get("Cookie"), touch=True)
                if not user:
                    return self.reply(401, {"error": "Sua sessão terminou. Entre novamente."})
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), user["csrf"]):
                    return self.reply(403, {"error": "Atualize a sessão antes de continuar."})
                if self.path == "/api/activity":
                    con.commit()
                    return self.reply(200, {"ok": True})
                if self.path == "/api/logout":
                    con.execute("DELETE FROM sessions WHERE digest=?", (user["digest"],))
                    access.audit(con, user, "Saiu do sistema")
                    con.commit()
                    return self.reply(
                        200, {"ok": True}, headers={"Set-Cookie": self.session_cookie("", True)}
                    )
                if self.path == "/api/password":
                    if not access.verify(data.get("currentPassword"), user["password"]):
                        raise ValueError("Senha atual inválida.")
                    if data.get("newPassword") == data.get("currentPassword"):
                        raise ValueError("Escolha uma senha diferente da atual.")
                    con.execute(
                        "UPDATE users SET password=?,must_change=0 WHERE id=?",
                        (access.hash_password(data.get("newPassword")), user["id"]),
                    )
                    con.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
                    access.audit(con, user, "Senha alterada")
                    con.commit()
                    return self.reply(
                        200, {"ok": True}, headers={"Set-Cookie": self.session_cookie("", True)}
                    )
                if user["must_change"]:
                    return self.reply(
                        403, {"error": "Troque sua senha temporária antes de continuar."}
                    )
                if self.path in ("/api/users/create", "/api/users/update"):
                    if user["role"] != "admin":
                        return self.reply(403, {"error": "Acesso exclusivo de administradores."})
                    if self.path.endswith("create"):
                        employee = data.get("employeeId")
                        if employee and not any(
                            e["id"] == employee and e.get("active", True)
                            for e in json.loads(
                                con.execute("SELECT payload FROM state WHERE id=1").fetchone()[0]
                            ).get("employees", [])
                        ):
                            raise ValueError("Selecione um funcionário ativo.")
                        access.create_user(con, data, user)
                    else:
                        access.update_user(con, data, user)
                    con.commit()
                    return self.reply(200, {"ok": True})
                if self.path not in ("/api/changes", "/api/state"):
                    return self.reply(404, {"error": "Não encontrado."})
                revision, payload = con.execute(
                    "SELECT revision,payload FROM state WHERE id=1"
                ).fetchone()
                old = self.runtime.defaults(dict(json.loads(payload), revision=revision))
                if self.path == "/api/changes":
                    candidate = access.apply_changes(old, data.get("changes"))
                    summary = ", ".join(
                        f"{c['key']}:{c.get('id', 'config')}" for c in data["changes"]
                    )
                else:
                    if type(data.get("revision")) is not int or data["revision"] != revision:
                        raise access.Conflict("Os dados mudaram. Atualize antes de continuar.")
                    candidate, summary = data, "Atualização completa"
                if user["role"] != "admin":
                    for key in ("company", "warningDays", "employees"):
                        if candidate.get(key) != old.get(key):
                            return self.reply(
                                403,
                                {
                                    "error": "Somente administradores alteram empresa, configurações ou funcionários."
                                },
                            )
                operations.sign_changes(candidate, old, user)
                clean = self.runtime.validate(candidate, old)
                con.execute(
                    "UPDATE state SET revision=?,payload=? WHERE id=1",
                    (revision + 1, json.dumps(clean, ensure_ascii=False)),
                )
                access.audit(con, user, "Dados alterados", f"Revisão {revision + 1}: " + summary)
                con.commit()
                try:
                    backup(self.runtime)
                except OSError as exc:
                    print("Falha no backup diário:", exc, flush=True)
                return self.reply(200, dict(clean, revision=revision + 1))
        except access.Conflict as exc:
            self.reply(409, {"error": str(exc)})
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception:
            import traceback

            traceback.print_exc()
            self.reply(
                500, {"error": "Não foi possível concluir. Consulte os registros do servidor."}
            )
