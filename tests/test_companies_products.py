import copy
import unittest
from datetime import date
import services
import operations
from tests import test_services
from tests import test_operations
from tests.test_network import Client


class ServiceCompanies(unittest.TestCase):
    setUp = test_services.ServiceHTTP.setUp
    tearDown = test_services.ServiceHTTP.tearDown
    registries = test_services.ServiceHTTP.registries
    job = test_services.ServiceHTTP.job

    def test_companies_own_and_external_keep_services_separate(self):
        self.registries()
        status, company, _ = self.client.request(
            "/api/services/company/save",
            {
                "company": {"name": "Confecção Externa", "email": "compras@empresa.com.br"},
                "revision": 0,
            },
        )
        self.assertEqual(status, 200, company)
        for technique in ("Bordado", "DTF"):
            for cid in (services.OWN_COMPANY, company["id"]):
                status, job, _ = self.client.request(
                    "/api/services/save",
                    {
                        "job": self.job(
                            technique=technique,
                            companyId=cid,
                            unitCents=0 if cid == services.OWN_COMPANY else 500,
                            setupCents=0,
                        )
                    },
                )
                self.assertEqual(status, 200, job)
                self.assertEqual(job["clientId"], cid)
                self.assertEqual(
                    job["companyKind"], "internal" if cid == services.OWN_COMPANY else "external"
                )
            _, listing, _ = self.client.request(
                "/api/services?technique=" + technique + "&month=" + date.today().strftime("%Y-%m")
            )
            self.assertEqual(len(listing["jobs"]), 2)
            self.assertIn(company["id"], [c["id"] for c in listing["companies"]])
        _, exported, _ = self.client.request("/api/export")
        self.assertIn(
            "Confecção Externa", [company["name"] for company in exported["services"]["companies"]]
        )

    def test_company_conflict_inactive_and_permissions(self):
        self.registries()
        _, company, _ = self.client.request(
            "/api/services/company/save", {"company": {"name": "Empresa teste"}, "revision": 0}
        )
        status, _, _ = self.client.request(
            "/api/services/company/save", {"company": dict(company, active=False), "revision": 0}
        )
        self.assertEqual(status, 409)
        self.assertEqual(
            self.client.request(
                "/api/services/company/save",
                {"company": dict(company, active=False), "revision": 1},
            )[0],
            200,
        )
        self.assertEqual(
            self.client.request("/api/services/save", {"job": self.job(companyId=company["id"])})[
                0
            ],
            400,
        )
        self.assertEqual(
            Client(self.url).request(
                "/api/services/company/save", {"company": {"name": "Sem sessão"}}
            )[0],
            401,
        )
        self.assertEqual(
            self.client.request(
                "/api/services/company/save", {"company": {"name": "Teste"}}, csrf=False
            )[0],
            403,
        )


class ReadyProducts(unittest.TestCase):
    def test_whole_piece_reservations_and_consumption(self):
        old = test_operations.fixture()
        old["stock"] = [self.stock()]
        new = copy.deepcopy(old)
        row = dict(
            id="reservation",
            stockId="jaleco-m-branco",
            orderId="o1",
            itemId="i1",
            qtyMilli=1500,
            stage="Reservado",
            date=date.today().isoformat(),
            note="Separar jalecos",
        )
        new["reservations"] = [row]
        with self.assertRaisesRegex(ValueError, "inteiras"):
            test_operations.save(new, old)
        row["qtyMilli"] = 2000
        reserved = test_operations.save(new, old)
        self.assertEqual(operations.inventory(reserved, "jaleco-m-branco")["available"], 8000)
        consumed = copy.deepcopy(reserved)
        consumed["orders"][0]["items"][0]["approved"] = True
        consumed["reservations"][0]["stage"] = "Consumido"
        saved = test_operations.save(consumed, reserved)
        self.assertEqual(operations.inventory(saved, "jaleco-m-branco")["onHand"], 8000)

    def stock(self, **changes):
        return dict(
            dict(
                id="jaleco-m-branco",
                name="Jaleco",
                category="Produto pronto",
                productType="Jaleco",
                size="M",
                color="Branco",
                sku="JAL-M-BR",
                unit="un",
                openingMilli=10000,
                minimumMilli=2000,
                movements=[],
                active=True,
                notes="",
            ),
            **changes,
        )

    def test_balance_movement_and_material_compatibility(self):
        old = test_operations.fixture()
        new = copy.deepcopy(old)
        new["stock"] = [
            self.stock(),
            dict(id="tecido", name="Tecido", unit="m", openingMilli=1500, movements=[]),
        ]
        clean = test_operations.save(new, old)
        self.assertEqual(operations.inventory(clean, "jaleco-m-branco")["onHand"], 10000)
        newer = copy.deepcopy(clean)
        newer["stock"][0]["movements"].append(
            dict(
                id="saida",
                kind="Saída",
                qtyMilli=3000,
                date=date.today().isoformat(),
                reason="Venda de 3 jalecos",
            )
        )
        updated = test_operations.save(newer, clean)
        self.assertEqual(operations.inventory(updated, "jaleco-m-branco")["onHand"], 7000)
        self.assertEqual(updated["stock"][0]["size"], "M")
        newer["stock"][0]["movements"][0]["qtyMilli"] = 500
        with self.assertRaisesRegex(ValueError, "inteiras"):
            test_operations.save(newer, clean)

    def test_reject_fractional_wrong_unit_category_change_and_negative_stock(self):
        old = test_operations.fixture()
        for changes in (dict(openingMilli=500), dict(unit="kg"), dict(productType="Tecido")):
            new = copy.deepcopy(old)
            new["stock"] = [self.stock(**changes)]
            with self.assertRaises(ValueError):
                test_operations.save(new, old)
        new = copy.deepcopy(old)
        new["stock"] = [self.stock()]
        clean = test_operations.save(new, old)
        newer = copy.deepcopy(clean)
        newer["stock"][0]["category"] = "Material"
        with self.assertRaises(ValueError):
            test_operations.save(newer, clean)
        newer = copy.deepcopy(clean)
        newer["stock"][0]["movements"] = [
            dict(
                id="saida",
                kind="Saída",
                qtyMilli=11000,
                date=date.today().isoformat(),
                reason="Excesso",
            )
        ]
        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            test_operations.save(newer, clean)
