import copy
import http.cookiejar as cookiejar
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor
from unittest.mock import patch
import access
import network
import server


class Client:
    def __init__(self, url):
        self.url = url
        self.opener = build_opener(HTTPCookieProcessor(cookiejar.CookieJar()))
        self.csrf = ""

    def request(self, path, data=None, origin=True, csrf=True):
        # Older fixtures use username-only accounts. Provision them through the
        # new email confirmation flow while preserving their login identifiers.
        if (
            path in ("/api/setup", "/api/users/create")
            and isinstance(data, dict)
            and data.get("username")
            and "email" not in data
        ):
            payload = dict(data, email=data["username"] + "@example.test")
            with (
                patch("access.send_recovery") as send,
                patch.dict(
                    "os.environ",
                    {
                        "TRAME_SMTP_HOST": "smtp.example.test",
                        "TRAME_SMTP_FROM": "sender@example.test",
                    },
                ),
            ):
                response = self.request(path, payload, origin=origin, csrf=csrf)
            if response[0] == 200 and send.called:
                confirmation = self.request(
                    "/api/email/confirm",
                    {"email": payload["email"], "code": send.call_args.args[1]},
                )
                if confirmation[0] != 200:
                    raise AssertionError("Fixture email confirmation failed")
            return response
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            if origin:
                headers["Origin"] = self.url if origin is True else origin
            if csrf:
                headers["X-CSRF-Token"] = self.csrf
        request = Request(
            self.url + path, json.dumps(data).encode() if data is not None else None, headers
        )
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            if response.headers.get_content_type() == "application/json":
                body = json.loads(body)
            return response.status, body, response.headers

    def login(self, name="admin", password="uma-senha-forte-de-teste"):
        status, body, headers = self.request("/api/login", {"username": name, "password": password})
        if status == 200:
            self.csrf = body["csrf"]
        return status, body, headers


class NetworkFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=server.HOME)
        self.previous = server.DB
        server.DB = Path(self.temp.name) / "test.sqlite3"
        network.bootstrap(server)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.http.server_port}"
        self.client = Client(self.url)
        token = (server.DB.parent / "chave-primeiro-acesso.txt").read_text()
        self.assertEqual(
            self.client.request(
                "/api/setup",
                {
                    "token": token,
                    "name": "Administrador teste",
                    "username": "admin",
                    "password": "uma-senha-forte-de-teste",
                },
            )[0],
            200,
        )
        self.assertEqual(self.client.login()[0], 200)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DB = self.previous
        self.temp.cleanup()

    def state(self, client=None):
        return (client or self.client).request("/api/state")[1]

    def change(self, key, cid, before, after, client=None):
        return (client or self.client).request(
            "/api/changes", {"changes": [{"key": key, "id": cid, "before": before, "after": after}]}
        )

    def employee(self, employee_id=""):
        self.assertEqual(
            self.client.request(
                "/api/users/create",
                {
                    "name": "Funcionário teste",
                    "username": "funcionario",
                    "password": "temporaria-funcionario",
                    "role": "employee",
                    "employeeId": employee_id,
                },
            )[0],
            200,
        )
        c = Client(self.url)
        self.assertEqual(c.login("funcionario", "temporaria-funcionario")[0], 200)
        return c

    def activate_employee(self, employee_id=""):
        c = self.employee(employee_id)
        self.assertEqual(
            c.request(
                "/api/password",
                {
                    "currentPassword": "temporaria-funcionario",
                    "newPassword": "senha-pessoal-funcionario",
                },
            )[0],
            200,
        )
        self.assertEqual(c.login("funcionario", "senha-pessoal-funcionario")[0], 200)
        return c

    def test_unauthenticated_cannot_read_or_modify_business_or_download_database(self):
        c = Client(self.url)
        for path in ["/api/state", "/api/users", "/api/audit", "/api/qr?order=a", "/api/revision"]:
            self.assertEqual(c.request(path)[0], 401, path)
        self.assertEqual(c.request("/api/changes", {"changes": []})[0], 401)
        self.assertIn(b"Entre na sua conta", c.request("/")[1])
        self.assertEqual(self.client.request("/dados/radar.sqlite3")[0], 404)

    def test_cookie_csrf_origin_and_setup_lock(self):
        c = Client(self.url)
        status, body, headers = c.login()
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(c.request("/api/logout", {}, csrf=False)[0], 403)
        self.assertEqual(c.request("/api/logout", {}, origin=False)[0], 403)
        self.assertEqual(c.request("/api/logout", {}, origin="https://evil.test")[0], 403)
        self.assertEqual(c.request("/api/setup", {"token": "anything"})[0], 403)
        self.assertFalse((server.DB.parent / "chave-primeiro-acesso.txt").exists())

    def test_passwords_are_hashed_and_not_returned(self):
        rows = self.client.request("/api/users")[1]
        self.assertNotIn("password", rows[0])
        self.assertNotIn("csrf", rows[0])
        with closing(server.connect()) as con:
            hashed = con.execute("select password from users").fetchone()[0]
        self.assertNotIn("uma-senha", hashed)
        self.assertTrue(access.verify("uma-senha-forte-de-teste", hashed))

    def test_employee_must_change_temporary_password_and_old_sessions_revoked(self):
        c = self.employee()
        self.assertEqual(c.request("/api/state")[0], 403)
        self.assertEqual(
            c.request(
                "/api/password",
                {"currentPassword": "errada", "newPassword": "senha-pessoal-funcionario"},
            )[0],
            400,
        )
        self.assertEqual(
            c.request(
                "/api/password",
                {
                    "currentPassword": "temporaria-funcionario",
                    "newPassword": "senha-pessoal-funcionario",
                },
            )[0],
            200,
        )
        self.assertEqual(c.request("/api/state")[0], 401)
        self.assertEqual(c.login("funcionario", "senha-pessoal-funcionario")[0], 200)

    def test_employee_cannot_administer_even_by_direct_post(self):
        c = self.activate_employee()
        for path in ["/api/users", "/api/audit"]:
            self.assertEqual(c.request(path)[0], 403)
        self.assertEqual(c.request("/api/users/create", {"role": "admin"})[0], 403)
        old = self.state(c)
        self.assertEqual(
            self.change("company", None, old["company"], {"name": "alterada"}, c)[0], 403
        )
        data = copy.deepcopy(old)
        data["warningDays"] = 9
        self.assertEqual(c.request("/api/state", data)[0], 403)
        self.assertEqual(self.state()["warningDays"], 3)

    def test_disabled_user_loses_access_and_last_admin_is_preserved(self):
        c = self.activate_employee()
        users = self.client.request("/api/users")[1]
        u = next(u for u in users if u["role"] == "employee")
        self.assertEqual(self.client.request("/api/users/update", dict(u, active=False))[0], 200)
        self.assertEqual(c.request("/api/state")[0], 401)
        admin = next(u for u in users if u["role"] == "admin")
        self.assertEqual(
            self.client.request("/api/users/update", dict(admin, active=False))[0], 400
        )

    def test_disjoint_simultaneous_writes_merge_and_same_record_conflicts(self):
        second = Client(self.url)
        second.login()

        def write(i):
            return self.change(
                "clients",
                "c" + str(i),
                None,
                {"id": "c" + str(i), "name": "Cliente " + str(i), "active": True},
                self.client if i == 1 else second,
            )[0]

        with ThreadPoolExecutor(2) as executor:
            result = list(executor.map(write, [1, 2]))
        self.assertEqual(result, [200, 200])
        self.assertEqual(len(self.state()["clients"]), 2)
        client = self.state()["clients"][0]
        self.assertEqual(
            self.change("clients", client["id"], client, dict(client, name="Alterado"))[0], 200
        )
        self.assertEqual(
            self.change("clients", client["id"], client, dict(client, name="Sobrescrito"), second)[
                0
            ],
            409,
        )
        self.assertEqual(self.state()["clients"][0]["name"], "Alterado")
        audit = self.client.request("/api/audit")[1]
        self.assertTrue(any("clients:c" in r["details"] for r in audit))

    def test_expired_sessions_logout_and_throttle(self):
        with closing(server.connect()) as con:
            con.execute("UPDATE sessions SET touched=?", (time.time() - access.IDLE_SECONDS - 5,))
            con.commit()
        self.assertEqual(self.client.request("/api/state")[0], 401)
        c = Client(self.url)
        for _ in range(8):
            self.assertEqual(c.login(password="errada")[0], 401)
        self.assertEqual(c.login()[0], 429)

    def test_logout_invalidates_cookie_on_server(self):
        self.assertEqual(self.client.request("/api/logout", {})[0], 200)
        self.assertEqual(self.client.request("/api/state")[0], 401)

    def test_business_validation_rolls_back_whole_change(self):
        old = self.state()
        changes = [
            {"key": "company", "before": old["company"], "after": {"name": "Não salvar"}},
            {"key": "warningDays", "before": 3, "after": 99},
        ]
        self.assertEqual(self.client.request("/api/changes", {"changes": changes})[0], 400)
        self.assertEqual(self.state(), old)

    def test_employee_quote_os_payment_delivery_and_authenticated_print(self):
        from datetime import date, timedelta

        self.assertEqual(
            self.change(
                "employees",
                "executor",
                None,
                {"id": "executor", "name": "Funcionário teste", "sector": "Costura"},
            )[0],
            200,
        )
        c = self.activate_employee("executor")
        day = date.today().isoformat()
        due = (date.today() + timedelta(days=7)).isoformat()
        order = {
            "id": "flow",
            "client": "Teste completo autenticado",
            "kind": "quote",
            "archived": False,
            "entry": day,
            "due": due,
            "validUntil": due,
            "payments": [],
            "items": [
                {
                    "id": "model",
                    "type": "Camiseta",
                    "sizes": {"M": 6, "G": 4},
                    "image": "",
                    "approved": False,
                    "stage": "Aguardando",
                    "unitPriceCents": 5000,
                    "techniques": [],
                }
            ],
        }
        status, result, _ = self.change("orders", "flow", None, order, c)
        self.assertEqual(status, 200, result)

        def update(edit):
            old = copy.deepcopy(result["orders"][0])
            after = copy.deepcopy(old)
            edit(after)
            response = self.change("orders", "flow", old, after, c)
            self.assertEqual(response[0], 200, response[1])
            return response[1]

        result = update(lambda o: o.update(kind="order"))
        self.assertEqual(result["orders"][0]["osNumber"], 1)
        self.assertEqual(result["orders"][0]["quoteSnapshot"]["order"]["kind"], "quote")
        result = update(
            lambda o: o["payments"].append(
                {"id": "p1", "amountCents": 20000, "method": "Pix", "date": day}
            )
        )
        self.assertEqual(server.money(result["orders"][0])["status"], "Parcialmente pago")
        result = update(
            lambda o: o["items"][0].update(
                approved=True,
                approvalEvidence={
                    "name": "Cliente teste",
                    "date": day,
                    "channel": "Presencial",
                    "note": "Validação",
                },
            )
        )
        result = update(lambda o: o["items"][0].update(stage="Em produção"))
        result = update(
            lambda o: o["items"][0]["tasks"].append(
                {
                    "id": "sewing",
                    "sector": "Costura",
                    "employeeId": "executor",
                    "due": due,
                    "qty": 10,
                    "stage": "Pendente",
                }
            )
        )
        result = update(
            lambda o: o["items"][0]["tasks"][0].update(
                stage="Concluído",
                signature={"name": "Funcionário teste", "date": day, "confirmed": True},
            )
        )
        self.assertEqual(
            result["orders"][0]["items"][0]["tasks"][0]["signature"]["source"],
            "Responsável conectado",
        )
        result = update(lambda o: o["items"][0].update(stage="Pronto"))
        result = update(
            lambda o: o["payments"].append(
                {"id": "p2", "amountCents": 30000, "method": "Pix", "date": day}
            )
        )

        def deliver(o):
            o["items"][0]["deliveries"].append(
                {
                    "id": "delivery",
                    "date": day,
                    "receiver": "Cliente teste",
                    "sizes": {"M": 6, "G": 4},
                }
            )
            o["items"][0]["stage"] = "Entregue"

        result = update(deliver)
        self.assertEqual(result["orders"][0]["items"][0]["stage"], "Entregue")
        self.assertEqual(server.money(result["orders"][0])["balance"], 0)
        self.assertEqual(c.request("/print?id=flow&type=os")[0], 200)
        self.assertIn(b"<svg", c.request("/api/qr?order=flow")[1])


class TLSConfiguration(unittest.TestCase):
    def test_network_never_starts_with_cleartext_passwords(self):
        with self.assertRaises(ValueError):
            network.validate_configuration(
                {"bind": "0.0.0.0", "public_url": "", "cert": "", "key": ""}
            )
        self.assertTrue(
            network.validate_configuration(
                {
                    "bind": "0.0.0.0",
                    "public_url": "https://trame.empresa.local:18743",
                    "cert": "cert.pem",
                    "key": "key.pem",
                }
            )
        )
        self.assertFalse(
            network.validate_configuration(
                {"bind": "127.0.0.1", "public_url": "", "cert": "", "key": ""}
            )
        )

    def test_certificate_handshake_secure_cookie_and_hostname_validation(self):
        import ssl
        from configure_network import configure

        with tempfile.TemporaryDirectory(dir=server.HOME) as temp:
            root = Path(temp)
            configure(root, "trame-teste.local", "192.168.1.120")
            previous = server.DB
            server.DB = root / "tls.sqlite3"
            try:
                network.bootstrap(server)
                http = server.TrameHTTPServer(("127.0.0.1", 0), server.Handler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(
                    root / "certificados/servidor.pem", root / "certificados/servidor-chave.pem"
                )
                http.tls_context = context
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                try:
                    ca = ssl.DER_cert_to_PEM_cert(
                        (root / "certificados/autoridade.cer").read_bytes()
                    )
                    trusted = ssl.create_default_context(cadata=ca)
                    from urllib.request import HTTPSHandler

                    client = Client(f"https://localhost:{http.server_port}")
                    client.opener = build_opener(
                        HTTPCookieProcessor(cookiejar.CookieJar()), HTTPSHandler(context=trusted)
                    )
                    # Uma conexão que não inicia TLS não pode bloquear outros usuários.
                    with __import__("socket").create_connection(("127.0.0.1", http.server_port)):
                        self.assertEqual(client.request("/health")[0], 200)
                    token = (root / "chave-primeiro-acesso.txt").read_text()
                    self.assertEqual(
                        client.request(
                            "/api/setup",
                            {
                                "token": token,
                                "name": "Admin TLS",
                                "username": "admin",
                                "password": "uma-senha-forte-de-teste",
                            },
                        )[0],
                        200,
                    )
                    status, _, headers = client.login()
                    self.assertEqual(status, 200)
                    self.assertIn("; Secure", headers["Set-Cookie"])
                    self.assertEqual(client.request("/api/state")[0], 200)
                    with __import__("socket").create_connection(
                        ("127.0.0.1", http.server_port)
                    ) as sock:
                        with self.assertRaises(ssl.SSLCertVerificationError):
                            trusted.wrap_socket(sock, server_hostname="outro.local")
                finally:
                    http.shutdown()
                    http.server_close()
                    thread.join()
            finally:
                server.DB = previous


if __name__ == "__main__":
    unittest.main()
