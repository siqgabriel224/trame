"""SMTP lento/falho não deve bloquear a operação nem ativar contas."""

import os
import threading
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import access
import backups
import server
import test_network


class EmailConfiguration(unittest.TestCase):
    def test_missing_and_invalid_settings_are_reported_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(access.email_status()["configured"])
        with patch.dict(
            os.environ,
            {
                "TRAME_SMTP_HOST": "smtp.test",
                "TRAME_SMTP_FROM": "sender@example.test",
                "TRAME_SMTP_PORT": "bad",
            },
        ):
            self.assertFalse(access.email_status()["configured"])

    def test_connection_check_does_not_send_mail(self):
        with (
            patch.dict(
                os.environ,
                {
                    "TRAME_SMTP_HOST": "smtp.test",
                    "TRAME_SMTP_FROM": "sender@example.test",
                    "TRAME_SMTP_SECURITY": "starttls",
                    "TRAME_SMTP_PORT": "587",
                },
            ),
            patch("smtplib.SMTP") as factory,
        ):
            smtp = factory.return_value.__enter__.return_value
            smtp.noop.return_value = (250, b"OK")
            access.check_email_connection()
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once()
            smtp.send_message.assert_not_called()


class EmailDeliveryHTTP(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TRAME_SMTP_HOST": "smtp.example.test",
                "TRAME_SMTP_FROM": "sender@example.test",
                "TRAME_BACKUP_DIR": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.fixture = test_network.NetworkFlow()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_slow_delivery_does_not_block_other_writes(self):
        entered, release = threading.Event(), threading.Event()

        def slow_send(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise ValueError("test SMTP timeout")

        other = test_network.Client(self.fixture.url)
        self.assertEqual(other.login()[0], 200)
        with (
            patch("access.send_recovery", side_effect=slow_send),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            future = pool.submit(
                self.fixture.client.request, "/api/forgot-password", {"email": "admin@example.test"}
            )
            try:
                self.assertTrue(entered.wait(3))
                self.assertTrue(server.LOCK.acquire(blocking=False))
                server.LOCK.release()
                # This uses BEGIN IMMEDIATE: also detect a lingering SQLite write lock.
                self.assertEqual(other.request("/api/activity", {})[0], 200)
            finally:
                release.set()
            self.assertEqual(future.result()[0], 200)

    def test_failed_delivery_keeps_pending_account_and_allows_resend(self):
        data = {
            "name": "Pendente",
            "email": "pending@example.test",
            "password": "Senha-pendente-12345",
        }
        with patch("access.send_recovery", side_effect=ValueError("SMTP unavailable")):
            status, body, _ = self.fixture.client.request("/api/users/create", data)
        self.assertEqual(status, 503)
        self.assertTrue(body["emailPending"])
        with closing(server.connect()) as con, con:
            self.assertEqual(
                con.execute(
                    "SELECT email_verified FROM users WHERE email=?", (data["email"],)
                ).fetchone()[0],
                0,
            )
            con.execute("UPDATE email_verifications SET sent=0")
        with patch("access.send_recovery") as sender:
            self.assertEqual(
                self.fixture.client.request("/api/email/resend", {"email": data["email"]})[0], 200
            )
            code = sender.call_args.args[1]
        self.assertEqual(
            self.fixture.client.request(
                "/api/email/confirm", {"email": data["email"], "code": code}
            )[0],
            200,
        )

    def test_missing_smtp_does_not_commit_new_account(self):
        with patch.dict(os.environ, {"TRAME_SMTP_HOST": "", "TRAME_SMTP_FROM": ""}):
            status, session, _ = self.fixture.client.request("/api/session")
            self.assertFalse(session["emailDelivery"]["configured"])
            status, _, _ = self.fixture.client.request(
                "/api/users/create",
                {
                    "name": "Pendente",
                    "email": "missing@example.test",
                    "password": "Senha-pendente-12345",
                },
            )
            self.assertEqual(status, 400)
        with closing(server.connect()) as con, con:
            self.assertIsNone(
                con.execute("SELECT 1 FROM users WHERE email='missing@example.test'").fetchone()
            )

    def test_backup_status_is_admin_only(self):
        self.assertEqual(self.fixture.client.request("/api/backups")[0], 200)
        client = test_network.Client(self.fixture.url)
        self.assertEqual(client.request("/api/backups")[0], 401)

    def test_backup_failure_does_not_turn_committed_save_into_error(self):
        current = self.fixture.state()["warningDays"]
        with (
            patch.object(backups, "folder", return_value=server.DB.parent / "failed-backups"),
            patch.object(backups, "_snapshot", side_effect=OSError("disk full")),
        ):
            status, _, _ = self.fixture.change("warningDays", None, current, current + 1)
            self.assertEqual(status, 200)
            self.assertEqual(self.fixture.state()["warningDays"], current + 1)
            self.assertTrue(self.fixture.client.request("/api/backups")[1]["lastError"])


class BackupScheduler(unittest.TestCase):
    def test_periodic_copy_runs_without_request_and_outside_accept_loop(self):
        http = object.__new__(server.TrameHTTPServer)
        http.RequestHandlerClass = server.Handler
        with (
            patch.object(
                server.time,
                "monotonic",
                side_effect=[100, 100 + backups.INTERVAL_SECONDS, 101 + backups.INTERVAL_SECONDS],
            ),
            patch.object(server.network, "backup") as create,
        ):
            http.service_actions()
            create.assert_not_called()
            http.service_actions()
            http._backup_worker.join(timeout=2)
            create.assert_called_once_with(server.Handler.runtime)
            http.service_actions()
            self.assertEqual(create.call_count, 1)
