import json
import unittest
import test_review
import test_operations
from test_network import Client
import server
from contextlib import closing
from datetime import date


class RecordDeletion(unittest.TestCase):
    setUp = test_review.HTTPReview.setUp
    tearDown = test_review.HTTPReview.tearDown

    def seed(self):
        state = test_operations.fixture()
        state.update(
            clients=[dict(id="client", name="Cliente teste")],
            employees=[
                dict(id="employee", name="Funcionario teste", sector="Bordado", active=True)
            ],
            stock=[dict(id="stock", name="Tecido", unit="m", openingMilli=10000, movements=[])],
        )
        state["revision"] = 0
        status, data, _ = self.client.request("/api/state", state)
        self.assertEqual(status, 200, data)
        return data

    def delete(self, scope, id, revision, **changes):
        return self.client.request(
            "/api/records/delete",
            dict(scope=scope, id=id, revision=revision, confirmed=True, **changes),
        )

    def test_main_records_hidden_but_preserved_and_confirmation(self):
        state = self.seed()
        self.assertEqual(
            self.client.request(
                "/api/records/delete",
                dict(scope="clients", id="client", revision=state["revision"]),
            )[0],
            400,
        )
        self.assertEqual(
            Client(self.url).request("/api/records/delete", dict(scope="clients", id="client"))[0],
            401,
        )
        for scope, rid in [
            ("orders", "o1"),
            ("clients", "client"),
            ("employees", "employee"),
            ("stock", "stock"),
        ]:
            self.assertEqual(self.delete(scope, rid, state["revision"])[0], 200)
            _, state, _ = self.client.request("/api/state")
            self.assertFalse(any(row["id"] == rid for row in state[scope]))
        with closing(server.connect()) as con:
            raw = json.loads(con.execute("SELECT payload FROM state").fetchone()[0])
            self.assertTrue(raw["orders"][0]["_deleted"])
            self.assertTrue(raw["clients"][0]["_deleted"])
        state["company"]["name"] = "Mudança posterior"
        status, saved, _ = self.client.request("/api/state", state)
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["clients"], [])

    def test_model_exclusion_allows_later_order_edit(self):
        state = self.seed()
        self.assertEqual(self.delete("items", "i1", state["revision"])[0], 200)
        _, visible, _ = self.client.request("/api/state")
        self.assertFalse(any(i["id"] == "i1" for i in visible["orders"][0]["items"]))
        before = visible["orders"][0]
        after = dict(before, description="Editado depois da exclusão")
        status, data, _ = self.client.request(
            "/api/changes", dict(changes=[dict(key="orders", id="o1", before=before, after=after)])
        )
        self.assertEqual(status, 200, data)
        self.assertFalse(any(i["id"] == "i1" for i in data["orders"][0]["items"]))

    def test_services_companies_and_supplies(self):
        self.seed()
        today = date.today().isoformat()
        _, job, _ = self.client.request(
            "/api/services/save",
            dict(
                job=dict(
                    technique="Bordado",
                    companyId="__own_company__",
                    entryDate=today,
                    dueDate=today,
                    status="Em andamento",
                    lines=[dict(description="Frente", qtyMilli=1000, unitCents=100)],
                )
            ),
        )
        self.assertEqual(self.delete("services", job["id"], job["revision"])[0], 200)
        self.assertEqual(
            self.client.request("/api/services/save", dict(job=job, revision=job["revision"]))[0],
            400,
        )
        _, company, _ = self.client.request(
            "/api/services/company/save", dict(company=dict(name="Empresa teste"), revision=0)
        )
        _, supply, _ = self.client.request(
            "/api/services/embroidery-stock/save",
            dict(
                item=dict(name="Linha", category="Linha", unit="cone", openingMilli=1000),
                revision=0,
            ),
        )
        self.assertEqual(
            self.delete("serviceCompanies", company["id"], company["revision"])[0], 200
        )
        self.assertEqual(self.delete("embroideryStock", supply["id"], supply["revision"])[0], 200)
        status, result, _ = self.client.request("/api/services?technique=Bordado&month=2026-10")
        self.assertEqual(status, 200)
        self.assertNotIn(company["id"], [c["id"] for c in result["companies"]])
        self.assertEqual(result["embroideryStock"], [])
        self.assertEqual(
            self.client.request(
                "/api/services/embroidery-stock/save", dict(item=supply, revision=2)
            )[0],
            400,
        )
