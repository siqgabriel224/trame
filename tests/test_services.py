from datetime import date, timedelta
import unittest

import services
import server
from tests import test_review
import json
from contextlib import closing
from tests.test_network import Client


class ServiceHTTP(unittest.TestCase):
    setUp = test_review.HTTPReview.setUp
    tearDown = test_review.HTTPReview.tearDown

    def registries(self):
        data = server.defaults(
            {
                "orders": [],
                "warningDays": 3,
                "clients": [
                    {
                        "id": "c",
                        "name": "Cliente de serviços",
                        "document": "12.345.678/0001-90",
                        "seller": "Vendedora teste",
                    }
                ],
                "employees": [
                    {"id": "e", "name": "Executor teste", "sector": "Bordado", "active": True}
                ],
            }
        )
        data["revision"] = 0
        status, result, _ = self.client.request("/api/state", data)
        self.assertEqual(status, 200, result)
        # Service clients have their own registry, independent of garment clients.
        with closing(server.connect()) as con:
            company = dict(
                id="c",
                name="Cliente de serviços",
                document="12.345.678/0001-90",
                seller="Vendedora teste",
                kind="external",
                active=True,
                revision=1,
            )
            con.execute(
                "INSERT INTO service_companies VALUES(?,?,?)", ("c", 1, json.dumps(company))
            )
            con.commit()
        return result

    def job(self, **changes):
        current = date.today().isoformat()
        return dict(
            {
                "technique": "Bordado",
                "clientId": "c",
                "description": "Bordado em peças trazidas pelo cliente",
                "seller": "",
                "employeeId": "e",
                "entryDate": current,
                "completedDate": current,
                "status": "Concluído",
                "unit": "peça",
                "qtyMilli": 10000,
                "unitCents": 750,
                "setupCents": 2500,
            },
            **changes,
        )

    def create(self, client=None, **changes):
        status, result, _ = (client or self.client).request(
            "/api/services/save", {"job": self.job(**changes)}
        )
        self.assertEqual(status, 200, result)
        return result

    def listing(self, kind="Bordado", client=None):
        return (client or self.client).request(
            f"/api/services?technique={kind}&month={date.today():%Y-%m}"
        )

    def account(self, role):
        status, result, _ = self.client.request(
            "/api/users/create",
            {
                "username": role,
                "name": "Pessoa teste",
                "role": role,
                "password": "temporaria-servicos-2026",
            },
        )
        self.assertEqual(status, 200, result)
        client = Client(self.url)
        self.assertEqual(client.login(role, "temporaria-servicos-2026")[0], 200)
        self.assertEqual(
            client.request(
                "/api/password",
                {
                    "currentPassword": "temporaria-servicos-2026",
                    "newPassword": "pessoal-servicos-2026",
                },
            )[0],
            200,
        )
        self.assertEqual(client.login(role, "pessoal-servicos-2026")[0], 200)
        return client

    def test_service_permissions_and_password_csrf_origin_are_enforced(self):
        self.registries()
        anonymous = Client(self.url)
        self.assertEqual(self.listing(client=anonymous)[0], 401)
        employee = self.account("employee")
        self.assertEqual(self.listing(client=employee)[0], 403)
        self.assertEqual(employee.request("/api/services/save", {"job": self.job()})[0], 403)
        self.assertEqual(employee.request("/service-print?technique=Bordado&month=2026-10")[0], 403)
        self.assertEqual(employee.request("/api/export")[0], 403)
        operator = self.account("embroiderer")
        self.assertEqual(self.listing(client=operator)[0], 200)
        self.assertEqual(
            operator.request("/api/services/save", {"job": self.job()}, csrf=False)[0], 403
        )
        self.assertEqual(
            operator.request(
                "/api/services/save", {"job": self.job()}, origin="https://outro.example"
            )[0],
            403,
        )
        result = self.create(client=operator)
        self.assertEqual(result["createdBy"]["name"], "Pessoa teste")
        self.assertEqual(
            operator.request(
                "/api/services/reopen",
                {
                    "technique": "Bordado",
                    "month": f"{date.today():%Y-%m}",
                    "revision": 0,
                    "reason": "Teste",
                },
            )[0],
            403,
        )
        self.assertEqual(self.listing(kind="Outro")[0], 400)

    def test_avulso_number_price_seller_and_orders_are_separate(self):
        before = self.registries()
        first = self.create()
        dtf = self.create(technique="DTF", unit="metro", qtyMilli=1500, unitCents=101, setupCents=0)
        self.assertEqual(first["code"], "BORD-0001")
        self.assertEqual(first["totalCents"], 10000)
        self.assertEqual(first["seller"], "Vendedora teste")
        self.assertEqual(dtf["code"], "DTF-0001")
        self.assertEqual(dtf["totalCents"], 152)
        self.assertEqual(self.client.request("/api/state")[1], before)
        self.assertEqual(len(self.listing()[1]["jobs"]), 1)
        self.assertEqual(len(self.listing("DTF")[1]["jobs"]), 1)
        self.assertNotIn("services", self.client.request("/api/state")[1])
        exported = self.client.request("/api/export")[1]
        self.assertEqual(len(exported["services"]["jobs"]), 2)
        self.assertNotIn("users", exported)

    def test_revisions_payments_overpayment_and_void_history(self):
        self.registries()
        job = self.create()
        body = {
            "id": job["id"],
            "revision": job["revision"],
            "amountCents": 4000,
            "date": date.today().isoformat(),
            "method": "Pix",
        }
        status, paid, _ = self.client.request("/api/services/receive", body)
        self.assertEqual(status, 200, paid)
        self.assertEqual(paid["balanceCents"], 6000)
        self.assertEqual(self.client.request("/api/services/receive", body)[0], 409)
        self.assertEqual(
            self.client.request(
                "/api/services/receive", dict(body, revision=paid["revision"], amountCents=6001)
            )[0],
            400,
        )
        status, _, _ = self.client.request(
            "/api/services/save",
            {
                "job": dict(paid, status="Cancelado", cancelReason="Erro"),
                "revision": paid["revision"],
            },
        )
        self.assertEqual(status, 400)
        status, voided, _ = self.client.request(
            "/api/services/void-receipt",
            {
                "id": paid["id"],
                "revision": paid["revision"],
                "paymentId": paid["payments"][0]["id"],
                "reason": "Lançamento de teste duplicado",
            },
        )
        self.assertEqual(status, 200, voided)
        self.assertTrue(voided["payments"][0]["voided"])
        self.assertEqual(voided["receivedCents"], 0)
        self.assertEqual(voided["balanceCents"], 10000)

    def test_month_closing_is_snapshot_and_blocks_late_or_moved_entries(self):
        self.registries()
        job = self.create()
        self.create(status="Recebido", completedDate="", employeeId="")
        operator = self.account("embroiderer")
        args = {"technique": "Bordado", "month": f"{date.today():%Y-%m}", "revision": 0}
        status, closing, _ = operator.request("/api/services/close", args)
        self.assertEqual(status, 200, closing)
        self.assertEqual(len(closing["jobs"]), 1)
        self.assertEqual(closing["totalCents"], 10000)
        self.assertEqual(self.client.request("/api/services/close", args)[0], 409)
        self.assertEqual(
            self.client.request(
                "/api/services/save",
                {
                    "job": dict(job, status="Recebido", completedDate=""),
                    "revision": job["revision"],
                },
            )[0],
            400,
        )
        self.assertEqual(self.client.request("/api/services/save", {"job": self.job()})[0], 400)
        status, paid, _ = self.client.request(
            "/api/services/receive",
            {
                "id": job["id"],
                "revision": job["revision"],
                "amountCents": 10000,
                "date": date.today().isoformat(),
                "method": "Pix",
            },
        )
        self.assertEqual(status, 200, paid)
        listed = self.listing()[1]
        self.assertEqual(listed["closing"], closing)
        self.assertEqual(next(j for j in listed["jobs"] if j["id"] == job["id"])["balanceCents"], 0)
        self.assertEqual(
            self.client.request(
                "/api/services/reopen", dict(args, revision=closing["revision"], reason="")
            )[0],
            400,
        )
        status, reopened, _ = self.client.request(
            "/api/services/reopen",
            dict(args, revision=closing["revision"], reason="Conferência da matriz"),
        )
        self.assertEqual(status, 200, reopened)
        changed = dict(paid, description="Matriz corrigida")
        self.assertEqual(
            self.client.request(
                "/api/services/save", {"job": changed, "revision": paid["revision"]}
            )[0],
            200,
        )
        status, final, _ = self.client.request(
            "/api/services/close", dict(args, revision=reopened["revision"])
        )
        self.assertEqual(status, 200, final)
        self.assertEqual(len(final["history"]), 1)
        self.assertEqual(final["history"][0]["jobs"][0]["description"], job["description"])
        self.assertEqual(final["jobs"][0]["description"], "Matriz corrigida")

    def test_invalid_dates_quantities_responsible_and_forged_receipts_are_refused(self):
        self.registries()
        for changes in (
            {"qtyMilli": 0},
            {"qtyMilli": True},
            {"qtyMilli": 1.5},
            {"employeeId": ""},
            {"completedDate": (date.today() + timedelta(days=1)).isoformat()},
        ):
            self.assertEqual(
                self.client.request("/api/services/save", {"job": self.job(**changes)})[0], 400
            )
        result = self.create(payments=[{"amountCents": 999999}])
        self.assertEqual(result["receivedCents"], 0)
        self.assertEqual(result["payments"], [])
        self.assertEqual(self.listing()[0], 200)


class ServiceAmounts(unittest.TestCase):
    def test_fractional_units_round_half_cent_up(self):
        job = {
            "qtyMilli": 1500,
            "unitCents": 1,
            "setupCents": 10,
            "status": "Concluído",
            "payments": [],
        }
        self.assertEqual(services.amounts(job)["totalCents"], 12)


if __name__ == "__main__":
    unittest.main()
