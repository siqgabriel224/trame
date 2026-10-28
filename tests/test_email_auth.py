import os
import sqlite3
import time
import unittest
from unittest.mock import patch

import access


class EmailRecovery(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        access.schema(self.con)
        with patch("access.send_recovery"):
            self.uid = access.create_user(
                self.con,
                {"name": "Teste", "email": "Pessoa@Outlook.com", "password": "Senha-original-123"},
                first=True,
            )
        self.con.execute("UPDATE users SET email_verified=1")
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_email_login_and_duplicate(self):
        result, error = access.login(
            self.con, {"username": "PESSOA@OUTLOOK.COM", "password": "Senha-original-123"}, "local"
        )
        self.assertIsNone(error)
        self.assertEqual(result[1]["id"], self.uid)
        with self.assertRaises(ValueError):
            access.create_user(
                self.con,
                {"name": "Outro", "email": "pessoa@outlook.com", "password": "Senha-original-123"},
            )

    @patch.dict(
        os.environ, {"TRAME_SMTP_HOST": "smtp.example.com", "TRAME_SMTP_FROM": "envio@gmail.com"}
    )
    @patch("access.send_recovery")
    def test_recovery_once_and_session_revocation(self, send):
        access.login(
            self.con, {"username": "pessoa@outlook.com", "password": "Senha-original-123"}, "login"
        )
        data = {"email": "pessoa@outlook.com"}
        access.forgot_password(self.con, data, "request")
        code = send.call_args.args[1]
        self.assertNotIn(code, self.con.execute("SELECT digest FROM password_resets").fetchone()[0])
        with self.assertRaises(ValueError):
            access.reset_password(
                self.con, dict(data, code="ERRADO", newPassword="Nova-senha-12345"), "reset"
            )
        access.reset_password(
            self.con, dict(data, code=code, newPassword="Nova-senha-12345"), "reset"
        )
        self.assertEqual(self.con.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
        with self.assertRaises(ValueError):
            access.reset_password(
                self.con, dict(data, code=code, newPassword="Outra-senha-1234"), "reset"
            )
        self.assertIsNone(
            access.login(
                self.con, {"username": data["email"], "password": "Nova-senha-12345"}, "new"
            )[1]
        )

    @patch.dict(
        os.environ, {"TRAME_SMTP_HOST": "smtp.example.com", "TRAME_SMTP_FROM": "envio@gmail.com"}
    )
    @patch("access.send_recovery")
    def test_expiry_enumeration_and_limits(self, send):
        data = {"email": "pessoa@outlook.com"}
        response = access.forgot_password(self.con, data, "request")
        self.assertEqual(
            response, access.forgot_password(self.con, {"email": "ausente@gmail.com"}, "other")
        )
        code = send.call_args.args[1]
        self.con.execute("UPDATE password_resets SET expires=?", (time.time() - 1,))
        with self.assertRaises(ValueError):
            access.reset_password(
                self.con, dict(data, code=code, newPassword="Nova-senha-12345"), "reset"
            )
        for _ in range(3):
            access.forgot_password(self.con, data, "request")
        with self.assertRaisesRegex(ValueError, "Muitas tentativas"):
            access.forgot_password(self.con, data, "request")

    def test_legacy_schema(self):
        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,employee_id TEXT NOT NULL DEFAULT '',must_change INTEGER NOT NULL DEFAULT 0)"
        )
        access.schema(con)
        access.create_user(
            con,
            {"username": "antigo", "name": "Legado", "password": "Senha-original-123"},
            first=True,
        )
        self.assertIsNone(
            access.login(con, {"username": "antigo", "password": "Senha-original-123"}, "legacy")[1]
        )
        con.close()
