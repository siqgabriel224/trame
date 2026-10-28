import copy
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import server


def sample():
    return {
        "revision": 0,
        "warningDays": 3,
        "orders": [
            {
                "id": "o1",
                "client": "Cliente teste",
                "entry": "2026-10-25",
                "due": "2026-10-28",
                "items": [
                    {
                        "id": "i1",
                        "type": "Camiseta",
                        "sizes": {"P": 10, "M": 20, "G": 10},
                        "image": "",
                        "approved": False,
                        "stage": "Aguardando",
                    },
                    {
                        "id": "i2",
                        "type": "Jaqueta",
                        "sizes": {"M": 5, "G": 5},
                        "image": "",
                        "approved": False,
                        "stage": "Aguardando",
                    },
                ],
            }
        ],
    }


class Rules(unittest.TestCase):
    def test_new_items_pending_and_totals(self):
        data = server.validate(sample(), {"orders": []})
        self.assertEqual(sum(sum(i["sizes"].values()) for i in data["orders"][0]["items"]), 50)
        data["orders"][0]["items"][0]["approved"] = True
        with self.assertRaises(ValueError):
            server.validate(data, {"orders": []})

    def test_unapproved_cannot_produce(self):
        old = sample()
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["stage"] = "Em produção"
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_independent_approval(self):
        old = sample()
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0].update(approved=True, stage="Em produção")
        data = server.validate(new, old)
        self.assertFalse(data["orders"][0]["items"][1]["approved"])

    def test_replacement_needs_approval(self):
        old = sample()
        old["orders"][0]["items"][0]["approved"] = True
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["image"] = "data:image/png;base64,aGVsbG8="
        with self.assertRaises(ValueError):
            server.validate(new, old)
        new["orders"][0]["items"][0]["approved"] = False
        server.validate(new, old)

    def test_production_layout_locked(self):
        old = sample()
        old["orders"][0]["items"][0].update(approved=True, stage="Em produção")
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0].update(
            image="data:image/png;base64,aGVsbG8=", approved=False, stage="Aguardando"
        )
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_dates_grade_and_preservation(self):
        for change in ["dates", "grade", "remove"]:
            old = sample()
            new = copy.deepcopy(old)
            if change == "dates":
                new["orders"][0]["due"] = "2026-10-24"
            if change == "grade":
                new["orders"][0]["items"][0]["sizes"] = {"P": -1}
            if change == "remove":
                new["orders"] = []
            with self.assertRaises(ValueError):
                server.validate(new, old)

    def test_sqlite_survives_reopen(self):
        original = server.DB
        with tempfile.TemporaryDirectory(dir=server.ROOT) as folder:
            try:
                server.DB = Path(folder) / "test.sqlite3"
                with closing(server.connect()) as con:
                    import json

                    con.execute(
                        "UPDATE state SET revision=1,payload=? WHERE id=1", (json.dumps(sample()),)
                    )
                    con.commit()
                loaded = server.read_state()
                self.assertEqual(loaded["revision"], 1)
                self.assertEqual(loaded["orders"][0]["client"], "Cliente teste")
            finally:
                server.DB = original


class Commercial(unittest.TestCase):
    def order(self):
        data = server.defaults(sample())
        item = data["orders"][0]["items"][0]
        item["unitPriceCents"] = 3590
        item["techniques"] = [
            {
                "type": "Bordado",
                "unitCents": 500,
                "setupCents": 2500,
                "location": "Peito",
                "description": "Logo",
            },
            {"type": "Silk", "unitCents": 300, "setupCents": 1000},
            {"type": "DTF", "unitCents": 750, "setupCents": 0},
        ]
        return data

    def test_mixed_techniques_and_exact_totals(self):
        data = self.order()
        o = data["orders"][0]
        o.update(freightCents=1000, discountCents=1590)
        server.validate(data, {"orders": []})
        self.assertEqual(server.item_money(o["items"][0]), 209100)
        self.assertEqual(server.money(o)["total"], 208510)

    def test_unpaid_partial_paid(self):
        data = self.order()
        o = data["orders"][0]
        value = server.money(o)["total"]
        self.assertEqual(server.money(o)["status"], "Não pago")
        o["payments"] = [{"id": "p1", "date": "2026-10-25", "method": "Pix", "amountCents": 10000}]
        self.assertEqual(server.money(o)["status"], "Parcialmente pago")
        o["payments"].append(
            {"id": "p2", "date": "2026-10-25", "method": "Dinheiro", "amountCents": value - 10000}
        )
        self.assertEqual(server.money(o)["status"], "Pago")
        self.assertEqual(server.money(o)["balance"], 0)
        server.validate(data, {"orders": []})

    def test_reject_overpayment_negative_fractional_money(self):
        for mode in ["over", "negative", "fractional", "discount"]:
            data = self.order()
            o = data["orders"][0]
            if mode == "over":
                o["payments"] = [
                    {"id": "p", "date": "2026-10-25", "method": "Pix", "amountCents": 999999}
                ]
            if mode == "negative":
                o["items"][0]["unitPriceCents"] = -1
            if mode == "fractional":
                o["items"][0]["unitPriceCents"] = 35.9
            if mode == "discount":
                o["discountCents"] = 999999
            with self.assertRaises(ValueError):
                server.validate(data, {"orders": []})

    def test_void_preserves_history(self):
        old = self.order()
        old["orders"][0]["payments"] = [
            {
                "id": "p",
                "date": "2026-10-25",
                "method": "Pix",
                "amountCents": 10000,
                "note": "Entrada",
                "voided": False,
            }
        ]
        new = copy.deepcopy(old)
        new["orders"][0]["payments"][0].update(voided=True, voidReason="Lançamento duplicado")
        clean = server.validate(new, old)
        self.assertEqual(server.money(clean["orders"][0])["received"], 0)
        new["orders"][0]["payments"] = []
        with self.assertRaises(ValueError):
            server.validate(new, old)
        new = copy.deepcopy(old)
        new["orders"][0]["payments"][0]["amountCents"] = 9000
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_quote_number_and_conversion(self):
        data = self.order()
        o = data["orders"][0]
        o["kind"] = "quote"
        clean = server.validate(data, {"orders": []})
        self.assertEqual(clean["orders"][0]["quoteNumber"], 1)
        self.assertNotIn("osNumber", clean["orders"][0])
        new = copy.deepcopy(clean)
        new["orders"][0]["kind"] = "order"
        converted = server.validate(new, clean)
        self.assertEqual(converted["orders"][0]["osNumber"], 1)
        self.assertEqual(converted["orders"][0]["quoteNumber"], 1)
        self.assertEqual(converted["orders"][0]["items"], clean["orders"][0]["items"])
        self.assertEqual(converted["orders"][0]["quoteSnapshot"]["order"]["kind"], "quote")
        changed = copy.deepcopy(converted)
        changed["orders"][0]["items"][0]["unitPriceCents"] = 9999
        changed["orders"][0]["quoteSnapshot"] = {}
        saved = server.validate(changed, converted)
        self.assertEqual(
            saved["orders"][0]["quoteSnapshot"]["order"]["items"][0]["unitPriceCents"], 3590
        )

    def test_quote_cannot_produce_or_receive_payment(self):
        for mode in ["produce", "receive"]:
            old = self.order()
            old["orders"][0]["kind"] = "quote"
            new = copy.deepcopy(old)
            if mode == "produce":
                new["orders"][0]["items"][0].update(stage="Em produção", approved=True)
            else:
                new["orders"][0]["payments"] = [
                    {"id": "p", "date": "2026-10-25", "method": "Pix", "amountCents": 100}
                ]
            with self.assertRaises(ValueError):
                server.validate(new, old)

    def test_migration_preserves_old_embroidery(self):
        data = sample()
        data["orders"][0]["items"][0].update(embroidery=True, embroideryNotes="Logo no peito")
        migrated = server.defaults(data)
        self.assertEqual(
            migrated["orders"][0]["items"][0]["techniques"][0]["description"], "Logo no peito"
        )
        self.assertEqual(migrated["orders"][0]["osNumber"], 1)
        self.assertEqual(server.money(migrated["orders"][0])["total"], 0)

    def test_numbering_and_same_id_preserved(self):
        old = server.validate(self.order(), {"orders": []})
        new = copy.deepcopy(old)
        another = copy.deepcopy(new["orders"][0])
        another["id"] = "o2"
        another["items"][0]["id"] = "i3"
        another["items"][1]["id"] = "i4"
        another["osNumber"] = 999
        new["orders"].append(another)
        new["orders"][0]["osNumber"] = 444
        clean = server.validate(new, old)
        self.assertEqual([o["osNumber"] for o in clean["orders"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
