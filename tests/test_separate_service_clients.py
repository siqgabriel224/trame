import sqlite3
import unittest
from datetime import date
import json
import access
import services


class SeparateServiceClients(unittest.TestCase):
    def test_general_clients_not_imported_and_legacy_history_is_preserved(self):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        access.schema(con)
        services.schema(con)
        business = dict(
            company=dict(name="Minha confecção"),
            clients=[dict(id="general", name="Cliente da confecção")],
            employees=[],
        )
        self.assertEqual(
            [c["id"] for c in services.companies(con, business)], [services.OWN_COMPANY]
        )
        today = date.today().isoformat()
        job = dict(
            technique="Bordado",
            clientId="general",
            entryDate=today,
            dueDate=today,
            status="Em andamento",
            lines=[dict(description="Frente", qtyMilli=1000, unitCents=100)],
        )
        actor = dict(id="a", name="Administrador", role="admin")
        with self.assertRaisesRegex(ValueError, "empresa cadastrada"):
            services.save(con, dict(job=job), actor, business)
        internal = services.save(
            con, dict(job=dict(job, clientId=services.OWN_COMPANY)), actor, business
        )
        self.assertEqual(internal["companyKind"], "internal")
        legacy = dict(
            internal,
            id="legacy",
            number=2,
            code="BORD-0002",
            clientId="general",
            companyId="general",
            client="Cliente da confecção",
        )
        con.execute(
            "INSERT INTO service_jobs VALUES(?,?,?,?,?,?)",
            ("legacy", "Bordado", 2, 1, today[:7], json.dumps(legacy)),
        )
        listing = services.listing(con, "Bordado", today[:7], business)
        historical = next(j for j in listing["jobs"] if j["id"] == "legacy")
        self.assertEqual(historical["companyId"], services.OWN_COMPANY)
        self.assertEqual(historical["client"], "Cliente da confecção")
        self.assertEqual(
            json.loads(
                con.execute("SELECT payload FROM service_jobs WHERE id='legacy'").fetchone()[0]
            )["companyId"],
            "general",
        )
        self.assertNotIn("general", [c["id"] for c in listing["companies"]])
