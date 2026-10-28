import sqlite3
import unittest
from unittest.mock import patch
import access
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
import server
import network
from tests.test_network import Client


class EmailVerification(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        access.schema(self.con)
        self.send = patch("access.send_recovery").start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.con.close()

    def create(self, email):
        uid = access.create_user(
            self.con, dict(name="Teste", email=email, password="Senha-teste-12345"), first=True
        )
        self.con.commit()
        return uid, self.send.call_args.args[1]

    def test_provider_activation_and_single_use(self):
        for provider in ["gmail.com", "outlook.com", "empresa.com.br"]:
            email = "teste@" + provider
            uid, code = self.create(email)
            self.assertIsNone(
                access.login(
                    self.con, dict(username=email, password="Senha-teste-12345"), provider
                )[0]
            )
            self.assertNotEqual(
                self.con.execute(
                    "SELECT digest FROM email_verifications WHERE user_id=?", (uid,)
                ).fetchone()[0],
                code,
            )
            access.confirm_email(self.con, dict(email=email, code=code), provider)
            self.assertIsNotNone(
                access.login(
                    self.con, dict(username=email, password="Senha-teste-12345"), provider
                )[0]
            )
            with self.assertRaises(ValueError):
                access.confirm_email(self.con, dict(email=email, code=code), provider)

    def test_invalid_expired_resend_and_wrong_email(self):
        uid, old = self.create("teste@gmail.com")
        with self.assertRaises(ValueError):
            access.confirm_email(self.con, dict(email="outro@gmail.com", code=old), "a")
        with self.assertRaises(ValueError):
            access.confirm_email(self.con, dict(email="teste@gmail.com"), "b", resend=True)
        self.con.execute("UPDATE email_verifications SET expires=0,sent=0")
        self.con.commit()
        with self.assertRaises(ValueError):
            access.confirm_email(self.con, dict(email="teste@gmail.com", code=old), "c")
        access.confirm_email(self.con, dict(email="teste@gmail.com"), "d", resend=True)
        new = self.send.call_args.args[1]
        self.assertNotEqual(old, new)
        with self.assertRaises(ValueError):
            access.confirm_email(self.con, dict(email="teste@gmail.com", code=old), "e")
        access.confirm_email(self.con, dict(email="teste@gmail.com", code=new), "f")

    def test_recovery_cannot_activate_pending_and_attempts_are_limited(self):
        self.create("teste@outlook.com")
        self.send.reset_mock()
        with patch.dict(
            "os.environ", {"TRAME_SMTP_HOST": "test", "TRAME_SMTP_FROM": "sender@example.com"}
        ):
            access.forgot_password(self.con, dict(email="teste@outlook.com"), "r")
        self.send.assert_not_called()
        for _ in range(5):
            with self.assertRaises(ValueError):
                access.confirm_email(self.con, dict(email="teste@outlook.com", code="ERRADO"), "x")
        with self.assertRaisesRegex(ValueError, "Muitas tentativas"):
            access.confirm_email(self.con, dict(email="teste@outlook.com", code="ERRADO"), "x")

    def test_pending_admin_cannot_replace_last_confirmed_admin(self):
        admin = access.create_user(
            self.con, dict(name="Admin", username="admin", password="Senha-teste-12345"), first=True
        )
        self.create("pendente@gmail.com")
        self.con.row_factory = sqlite3.Row
        user = dict(self.con.execute("SELECT * FROM users WHERE id=?", (admin,)).fetchone())
        with self.assertRaisesRegex(ValueError, "administrador"):
            access.delete_account(
                self.con,
                user,
                dict(
                    currentPassword="Senha-teste-12345", acknowledged=True, confirmation="EXCLUIR"
                ),
            )


class VerificationHTTP(unittest.TestCase):
    def test_setup_create_confirm_and_login(self):
        previous = server.DB
        with tempfile.TemporaryDirectory(dir=server.HOME) as folder:
            server.DB = Path(folder) / "test.sqlite3"
            http = None
            try:
                network.bootstrap(server)
                http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                client = Client("http://127.0.0.1:" + str(http.server_port))
                token = (server.DB.parent / "chave-primeiro-acesso.txt").read_text()
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
                    status, _, _ = client.request(
                        "/api/setup",
                        dict(
                            token=token,
                            name="Admin",
                            email="admin@gmail.com",
                            password="Senha-teste-12345",
                        ),
                    )
                    self.assertEqual(status, 200)
                    code = send.call_args.args[1]
                    self.assertEqual(client.login("admin@gmail.com", "Senha-teste-12345")[0], 401)
                    self.assertEqual(
                        client.request(
                            "/api/email/confirm",
                            dict(email="admin@gmail.com", code=code),
                            origin=False,
                        )[0],
                        403,
                    )
                    self.assertEqual(
                        client.request(
                            "/api/email/confirm", dict(email="admin@gmail.com", code=code)
                        )[0],
                        200,
                    )
                    self.assertEqual(client.login("admin@gmail.com", "Senha-teste-12345")[0], 200)
                    self.assertEqual(
                        client.request(
                            "/api/users/create",
                            dict(
                                name="Funcionario",
                                email="pessoa@outlook.com",
                                password="Senha-teste-12345",
                            ),
                        )[0],
                        200,
                    )
                    employeeCode = send.call_args.args[1]
                    employee = Client(client.url)
                    self.assertEqual(
                        employee.login("pessoa@outlook.com", "Senha-teste-12345")[0], 401
                    )
                    self.assertEqual(
                        employee.request(
                            "/api/email/confirm",
                            dict(email="pessoa@outlook.com", code=employeeCode),
                        )[0],
                        200,
                    )
                    self.assertEqual(
                        employee.login("pessoa@outlook.com", "Senha-teste-12345")[0], 200
                    )
            finally:
                if http:
                    http.shutdown()
                    http.server_close()
                    thread.join()
                server.DB = previous
