import sqlite3
import unittest

import access
from test_network import NetworkFlow


class AccountDeletion(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        access.schema(self.con)
        self.admin = self.create("admin", "admin")
        self.employee = self.create("employee", "employee")
        self.data = dict(currentPassword="senha-teste-123456", acknowledged=True)

    def create(self, login, role):
        uid = access.create_user(
            self.con, dict(username=login, name=login, password="senha-teste-123456", role=role)
        )
        self.con.row_factory = sqlite3.Row
        return dict(self.con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

    def tearDown(self):
        self.con.close()

    def test_requires_ack_confirmation_and_password(self):
        for change in [
            dict(acknowledged=False),
            dict(acknowledged="true"),
            dict(currentPassword="errada"),
        ]:
            with self.assertRaises(ValueError):
                access.delete_account(self.con, self.employee, dict(self.data, **change))
            self.assertIsNotNone(
                self.con.execute(
                    "SELECT 1 FROM users WHERE id=?", (self.employee["id"],)
                ).fetchone()
            )

    def test_last_admin_and_actual_deletion(self):
        with self.assertRaisesRegex(ValueError, "administrador"):
            access.delete_account(self.con, self.admin, self.data)
        access.login(
            self.con, dict(username="employee", password=self.data["currentPassword"]), "test"
        )
        self.con.execute(
            "INSERT INTO password_resets VALUES(?,?,?)", (self.employee["id"], "fake", 99999999999)
        )
        access.delete_account(self.con, self.employee, self.data)
        for table, field in [
            ("users", "id"),
            ("sessions", "user_id"),
            ("password_resets", "user_id"),
        ]:
            self.assertEqual(
                self.con.execute(
                    "SELECT count(*) FROM " + table + " WHERE " + field + "=?",
                    (self.employee["id"],),
                ).fetchone()[0],
                0,
            )
        self.assertIsNotNone(
            self.con.execute(
                "SELECT 1 FROM audit WHERE user_id=?", (self.employee["id"],)
            ).fetchone()
        )
        self.create("otheradmin", "admin")
        access.delete_account(self.con, self.admin, self.data)

    def test_export_omits_secrets_and_other_users(self):
        exported = access.export_account(self.con, self.employee)
        self.assertEqual(exported["account"]["id"], self.employee["id"])
        self.assertNotIn("password", exported["account"])
        self.assertNotIn("csrf", exported["account"])
        self.assertEqual(len(exported["activity"]), 1)
        self.assertNotIn("details", exported["activity"][0])


class AccountDeletionHTTP(NetworkFlow):
    # Reuse the isolated HTTP fixture without duplicating its inherited tests.
    def test_account_routes(self):
        self.assertEqual(self.client.request("/api/account/export", {}, csrf=False)[0], 403)
        status, body, _ = self.client.request("/api/account/export", {})
        self.assertEqual(status, 200)
        self.assertNotIn("password", body["account"])
        self.assertEqual(
            self.client.request(
                "/api/account/delete",
                dict(
                    currentPassword="uma-senha-forte-de-teste",
                    acknowledged=True,
                    confirmation="EXCLUIR",
                ),
            )[0],
            400,
        )


# Expose only the new HTTP case when running this module.
def load_tests(loader, tests, pattern):
    result = loader.loadTestsFromTestCase(AccountDeletion)
    result.addTest(AccountDeletionHTTP("test_account_routes"))
    return result
