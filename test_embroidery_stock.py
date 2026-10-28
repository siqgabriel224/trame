import unittest
from datetime import date
import test_services
from test_network import Client


class EmbroideryStock(unittest.TestCase):
    setUp = test_services.ServiceHTTP.setUp
    tearDown = test_services.ServiceHTTP.tearDown

    def create(self):
        status, row, _ = self.client.request(
            "/api/services/embroidery-stock/save",
            dict(
                item=dict(
                    name="Linha branca",
                    category="Linha",
                    unit="cone",
                    openingMilli=5000,
                    minimumMilli=2000,
                    color="Branco",
                    code="001",
                ),
                revision=0,
            ),
        )
        self.assertEqual(status, 200, row)
        return row

    def test_inventory_history_conflicts_export_and_isolation(self):
        status, palette, _ = self.client.request("/api/thread-colors")
        self.assertEqual(status, 200)
        self.assertEqual(palette["colors"]["2228"]["position"], "9N")
        self.assertEqual(len(palette["colors"]), 286)
        self.assertEqual(Client(self.url).request("/api/thread-colors")[0], 401)
        item = self.create()
        movement = dict(
            id=item["id"],
            revision=1,
            kind="Saída",
            qtyMilli=4000,
            date=date.today().isoformat(),
            reason="Consumo no bordado",
        )
        self.assertEqual(
            self.client.request("/api/services/embroidery-stock/move", movement)[0], 200
        )
        self.assertEqual(
            self.client.request("/api/services/embroidery-stock/move", movement)[0], 409
        )
        for technique in ["Bordado", "DTF"]:
            _, data, _ = self.client.request(
                "/api/services?technique=" + technique + "&month=" + date.today().strftime("%Y-%m")
            )
            if technique == "Bordado":
                self.assertEqual(data["embroideryStock"][0]["balanceMilli"], 1000)
                self.assertEqual(len(data["embroideryStock"][0]["movements"]), 1)
            else:
                self.assertEqual(data["embroideryStock"], [])
        _, business, _ = self.client.request("/api/state")
        self.assertEqual(business["stock"], [])
        _, exported, _ = self.client.request("/api/export")
        self.assertEqual(len(exported["services"]["embroideryStock"]), 1)

    def test_validation_permissions_and_immutable_opening(self):
        item = self.create()
        movement = dict(
            id=item["id"],
            revision=1,
            kind="Saída",
            qtyMilli=6000,
            date=date.today().isoformat(),
            reason="Teste",
        )
        self.assertEqual(
            self.client.request("/api/services/embroidery-stock/move", movement)[0], 400
        )
        self.assertEqual(
            self.client.request(
                "/api/services/embroidery-stock/move", dict(movement, qtyMilli=1000, reason="")
            )[0],
            400,
        )
        self.assertEqual(
            self.client.request(
                "/api/services/embroidery-stock/save",
                dict(item=dict(item, openingMilli=1000), revision=1),
            )[0],
            400,
        )
        self.assertEqual(
            self.client.request(
                "/api/services/embroidery-stock/save",
                dict(item=dict(item, notes="Correção"), revision=1),
            )[0],
            200,
        )
        self.assertEqual(
            Client(self.url).request("/api/services/embroidery-stock/move", movement)[0], 401
        )
        self.assertEqual(
            self.client.request("/api/services/embroidery-stock/move", movement, csrf=False)[0], 403
        )
