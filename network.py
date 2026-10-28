"""HTTP autenticado para um servidor central da rede interna."""

import hmac
import hashlib
import ipaddress
import json
import os
import secrets
import ssl
from contextlib import closing
from urllib.parse import urlsplit, quote, parse_qs
import access
import cnpj
import operations
import services
import backups
import layouts


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
    return backups.create(runtime)


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
        if getattr(self, "_capture_reply", False):
            self._pending_reply = (status, value, mime, headers)
            return
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
                        "emailDelivery": access.email_status(),
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
            if path == "/api/backups":
                if user["role"] != "admin":
                    return self.reply(403, {"error": "Acesso exclusivo de administradores."})
                return self.reply(200, backups.status(self.runtime))
            if path == "/api/thread-colors":
                if not services.allowed(user):
                    return self.reply(403, {"error": "Acesso exclusivo ao estoque de bordado."})
                return self.reply(200, services.thread_palette())
            if path in ("/api/services", "/service-print"):
                if not services.allowed(user):
                    return self.reply(
                        403,
                        {
                            "error": "Bordado e DTF são exclusivos do administrador e do perfil Bordador(a)."
                        },
                    )
                if path == "/api/services":
                    params = parse_qs(urlsplit(self.path).query)
                    try:
                        result = services.listing(
                            con,
                            params.get("technique", [""])[0],
                            params.get("month", [""])[0],
                            self.runtime.read_state(),
                        )
                        return self.reply(200, result)
                    except (ValueError, TypeError) as exc:
                        return self.reply(400, {"error": str(exc)})
            if path == "/api/export":
                if user["role"] != "admin":
                    return self.reply(
                        403, {"error": "A exportação completa é exclusiva do administrador."}
                    )
                return self.reply(
                    200, dict(self.runtime.read_state(), services=services.export(con))
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
        limit = (
            120000000
            if self.path in ("/api/state", "/api/changes")
            else 65536
            if self.path == "/api/services/save"
            else 16384
        )
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
        # Libera a transação e o bloqueio antes de acessar o SMTP.
        self._capture_reply = True
        self._pending_reply = None
        response = None
        try:
            with access.deferred_mail() as messages:
                self.handle_post()
            response = self._pending_reply
            if (
                response
                and response[0] < 400
                and self.path not in ("/api/activity", "/api/login", "/api/logout")
            ):
                backup(self.runtime)
            if response and response[0] < 400:
                for email, code, verification in messages:
                    try:
                        access.send_recovery(email, code, verification=verification)
                    except ValueError:
                        response = (
                            503,
                            {
                                "error": "Não foi possível entregar o e-mail. A solicitação foi salva. Se for uma conta nova ou alteração de e-mail, use Confirmar meu e-mail → Reenviar código após conferir o envio no servidor. Para recuperar a senha, solicite outro código.",
                                "emailPending": True,
                            },
                            "application/json; charset=utf-8",
                            None,
                        )
                        break
        finally:
            self._capture_reply = False
        if response:
            self.reply(*response)

    def handle_post(self):
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
                if self.path in ("/api/email/confirm", "/api/email/resend"):
                    return self.reply(
                        200,
                        access.confirm_email(
                            con, data, self.client_address[0], resend=self.path.endswith("resend")
                        ),
                    )
                if self.path in ("/api/forgot-password", "/api/reset-password"):
                    action = (
                        access.forgot_password
                        if self.path == "/api/forgot-password"
                        else access.reset_password
                    )
                    return self.reply(200, action(con, data, self.client_address[0]))
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
                    access.email_address(data.get("email"))
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
                if self.path == "/api/account/export":
                    result = access.export_account(con, user)
                    con.commit()
                    return self.reply(200, result)
                if self.path == "/api/account/delete":
                    access.delete_account(con, user, data)
                    con.commit()
                    return self.reply(
                        200, {"ok": True}, headers={"Set-Cookie": self.session_cookie("", True)}
                    )
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
                    con.execute("DELETE FROM password_resets WHERE user_id=?", (user["id"],))
                    access.audit(con, user, "Senha alterada")
                    con.commit()
                    return self.reply(
                        200, {"ok": True}, headers={"Set-Cookie": self.session_cookie("", True)}
                    )
                if user["must_change"]:
                    return self.reply(
                        403, {"error": "Troque sua senha temporária antes de continuar."}
                    )
                if self.path == "/api/records/delete":
                    result = access.delete_record(con, data, user, self.runtime)
                    con.commit()
                    return self.reply(200, result)
                if self.path.startswith("/api/services/"):
                    if not services.allowed(user):
                        return self.reply(
                            403,
                            {
                                "error": "Bordado e DTF são exclusivos do administrador e do perfil Bordador(a)."
                            },
                        )
                    if self.path == "/api/services/reopen" and user["role"] != "admin":
                        return self.reply(
                            403, {"error": "Somente o administrador reabre um fechamento."}
                        )
                    business = self.runtime.defaults(
                        json.loads(
                            con.execute("SELECT payload FROM state WHERE id=1").fetchone()[0]
                        )
                    )
                    if self.path == "/api/services/embroidery-stock/save":
                        result = services.embroidery_stock_save(con, data, user)
                    elif self.path == "/api/services/embroidery-stock/move":
                        result = services.embroidery_stock_move(con, data, user)
                    elif self.path == "/api/services/company/save":
                        result = services.save_company(con, data, user)
                    elif self.path == "/api/services/save":
                        result = services.save(con, data, user, business)
                    elif self.path in ("/api/services/receive", "/api/services/void-receipt"):
                        result = services.receive(
                            con, data, user, void=self.path.endswith("void-receipt")
                        )
                    elif self.path in ("/api/services/close", "/api/services/reopen"):
                        result = services.close(
                            con, data, user, business, reopen=self.path.endswith("reopen")
                        )
                    else:
                        return self.reply(404, {"error": "Operação de serviço não encontrada."})
                    con.commit()
                    return self.reply(200, result)
                if self.path in ("/api/users/create", "/api/users/update"):
                    if user["role"] != "admin":
                        return self.reply(403, {"error": "Acesso exclusivo de administradores."})
                    if self.path.endswith("create"):
                        access.email_address(data.get("email"))
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
                if self.headers.get("X-Trame-Layouts") == "links":
                    layouts.restore_submission(data, old, changes=self.path == "/api/changes")
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
                access.preserve_excluded(candidate, old)
                operations.sign_changes(candidate, old, user)
                clean = self.runtime.validate(candidate, old)
                con.execute(
                    "UPDATE state SET revision=?,payload=? WHERE id=1",
                    (revision + 1, json.dumps(clean, ensure_ascii=False)),
                )
                access.audit(con, user, "Dados alterados", f"Revisão {revision + 1}: " + summary)
                con.commit()
                visible = access.visible_state(dict(clean, revision=revision + 1))
                if self.headers.get("X-Trame-Layouts") == "links":
                    visible = layouts.compact(visible)
                return self.reply(200, visible)
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
