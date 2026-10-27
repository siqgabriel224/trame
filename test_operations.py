import copy
import unittest
import server
import operations
from test_radar import sample


def fixture():
    data = server.defaults(sample())
    data["orders"][0]["items"][0]["unitPriceCents"] = 1000
    return data


def save(new, old):
    return server.validate(new, copy.deepcopy(old))


class Operations(unittest.TestCase):
    def test_client_registry_and_order_link(self):
        old = fixture()
        new = copy.deepcopy(old)
        new["clients"] = [
            {
                "id": "c",
                "name": "Cliente recorrente",
                "responsible": "Contato",
                "email": "teste@example.com",
            }
        ]
        new["orders"][0]["clientId"] = "c"
        clean = save(new, old)
        self.assertEqual(clean["orders"][0]["clientId"], "c")
        new = copy.deepcopy(clean)
        new["clients"] = []
        with self.assertRaises(ValueError):
            save(new, clean)
        new = copy.deepcopy(clean)
        new["orders"][0]["clientId"] = "inexistente"
        with self.assertRaises(ValueError):
            save(new, clean)

    def task_fixture(self):
        data = fixture()
        data["employees"] = [{"id": "e", "name": "Pessoa teste", "sector": "Bordado"}]
        data["orders"][0]["items"][0]["tasks"] = [
            {
                "id": "t",
                "sector": "Bordado",
                "employeeId": "e",
                "due": "2026-10-28",
                "qty": 40,
                "stage": "Pendente",
                "notes": "",
            }
        ]
        return data

    def test_sector_queue_requires_approval_and_employee(self):
        old = self.task_fixture()
        new = copy.deepcopy(old)
        i = new["orders"][0]["items"][0]
        i["tasks"][0]["stage"] = "Em andamento"
        with self.assertRaises(ValueError):
            save(new, old)
        i["approved"] = True
        clean = save(new, old)
        self.assertEqual(clean["orders"][0]["items"][0]["tasks"][0]["stage"], "Em andamento")
        i["tasks"][0]["employeeId"] = ""
        with self.assertRaises(ValueError):
            save(new, old)

    def test_task_quantity_and_history(self):
        old = self.task_fixture()
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["tasks"][0]["qty"] = 41
        with self.assertRaises(ValueError):
            save(new, old)
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["tasks"] = []
        with self.assertRaises(ValueError):
            save(new, old)

    def stock_fixture(self):
        data = fixture()
        data["stock"] = [
            {
                "id": "s",
                "name": "Tecido",
                "unit": "m",
                "openingMilli": 10000,
                "minimumMilli": 2000,
                "movements": [],
            }
        ]
        return data

    def reservation(self, qty=6500):
        return {
            "id": "r",
            "stockId": "s",
            "orderId": "o1",
            "itemId": "i1",
            "qtyMilli": qty,
            "stage": "Reservado",
            "date": "2026-10-25",
            "note": "Teste",
        }

    def test_reservation_and_available_stock(self):
        old = self.stock_fixture()
        new = copy.deepcopy(old)
        new["reservations"] = [self.reservation()]
        clean = save(new, old)
        self.assertEqual(
            operations.inventory(clean, "s"), {"onHand": 10000, "reserved": 6500, "available": 3500}
        )
        new["reservations"][0]["qtyMilli"] = 11000
        with self.assertRaises(ValueError):
            save(new, old)

    def test_consume_release_and_block_negative_stock(self):
        old = self.stock_fixture()
        old["reservations"] = [self.reservation()]
        new = copy.deepcopy(old)
        new["reservations"][0]["stage"] = "Consumido"
        with self.assertRaises(ValueError):
            save(new, old)
        new["orders"][0]["items"][0]["approved"] = True
        consumed = save(new, old)
        self.assertEqual(
            operations.inventory(consumed, "s"), {"onHand": 3500, "reserved": 0, "available": 3500}
        )
        new = copy.deepcopy(old)
        new["reservations"][0]["stage"] = "Liberado"
        released = save(new, old)
        self.assertEqual(operations.inventory(released, "s")["available"], 10000)
        new = copy.deepcopy(consumed)
        new["stock"][0]["movements"] = [
            {"id": "m", "date": "2026-10-25", "kind": "Saída", "qtyMilli": 4000, "reason": "Teste"}
        ]
        with self.assertRaises(ValueError):
            save(new, consumed)

    def test_stock_movement_is_preserved(self):
        old = self.stock_fixture()
        old["stock"][0]["movements"] = [
            {
                "id": "m",
                "date": "2026-10-25",
                "kind": "Entrada",
                "qtyMilli": 1250,
                "reason": "Compra",
            }
        ]
        new = copy.deepcopy(old)
        new["stock"][0]["movements"][0]["qtyMilli"] = 1300
        with self.assertRaises(ValueError):
            save(new, old)
        self.assertEqual(operations.inventory(old, "s")["available"], 11250)

    def delivery(self, id="d", sizes=None):
        return {
            "id": id,
            "date": "2026-10-25",
            "receiver": "Cliente teste",
            "notes": "",
            "sizes": sizes or {"P": 5, "M": 10, "G": 0},
            "voided": False,
        }

    def test_partial_delivery_and_final_delivery(self):
        old = fixture()
        old["orders"][0]["items"][0].update(approved=True, stage="Pronto")
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["deliveries"] = [self.delivery()]
        clean = save(new, old)
        self.assertEqual(
            operations.delivered(clean["orders"][0]["items"][0]), {"P": 5, "M": 10, "G": 0}
        )
        new = copy.deepcopy(clean)
        new["orders"][0]["items"][0]["deliveries"].append(
            self.delivery("d2", {"P": 5, "M": 10, "G": 10})
        )
        new["orders"][0]["items"][0]["stage"] = "Entregue"
        complete = save(new, clean)
        self.assertEqual(sum(operations.delivered(complete["orders"][0]["items"][0]).values()), 40)

    def test_overdelivery_and_false_completion_rejected(self):
        old = fixture()
        old["orders"][0]["items"][0].update(approved=True, stage="Pronto")
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["deliveries"] = [self.delivery(sizes={"P": 11})]
        with self.assertRaises(ValueError):
            save(new, old)
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["stage"] = "Entregue"
        with self.assertRaises(ValueError):
            save(new, old)

    def test_delivery_void_keeps_evidence(self):
        old = fixture()
        old["orders"][0]["items"][0].update(
            approved=True, stage="Pronto", deliveries=[self.delivery()]
        )
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["deliveries"][0].update(
            voided=True, voidReason="Lançamento incorreto"
        )
        clean = save(new, old)
        self.assertEqual(operations.delivered(clean["orders"][0]["items"][0]), {})
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["deliveries"][0]["receiver"] = "Outra pessoa"
        with self.assertRaises(ValueError):
            save(new, old)

    def test_legacy_delivered_orders_remain_delivered(self):
        data = sample()
        data["orders"][0]["items"][0].update(approved=True, stage="Entregue")
        normalized = server.defaults(data)
        self.assertEqual(
            sum(operations.delivered(normalized["orders"][0]["items"][0]).values()), 40
        )
        save(normalized, normalized)

    def installment_fixture(self):
        data = fixture()
        data["orders"][0]["installments"] = [
            {
                "id": "part",
                "label": "Parcela 1",
                "due": "2026-10-28",
                "amountCents": 20000,
                "cancelled": False,
            }
        ]
        return data

    def test_installments_receipt_balance_and_overpayment(self):
        old = self.installment_fixture()
        new = copy.deepcopy(old)
        o = new["orders"][0]
        o["payments"] = [
            {
                "id": "p",
                "date": "2026-10-25",
                "method": "Pix",
                "amountCents": 10000,
                "installmentId": "part",
            }
        ]
        clean = save(new, old)
        self.assertEqual(
            operations.installment_balance(
                clean["orders"][0], clean["orders"][0]["installments"][0]
            ),
            10000,
        )
        o["payments"][0]["amountCents"] = 20001
        with self.assertRaises(ValueError):
            save(new, old)

    def test_installment_plan_respects_existing_unallocated_payments(self):
        old = fixture()
        old["orders"][0]["payments"] = [
            {"id": "p", "date": "2026-10-25", "method": "Pix", "amountCents": 10000}
        ]
        new = copy.deepcopy(old)
        new["orders"][0]["installments"] = [
            {"id": "part", "label": "Saldo", "due": "2026-10-28", "amountCents": 30001}
        ]
        with self.assertRaises(ValueError):
            save(new, old)
        new["orders"][0]["installments"][0]["amountCents"] = 30000
        save(new, old)

    def test_cancel_received_installment_rejected(self):
        old = self.installment_fixture()
        old["orders"][0]["payments"] = [
            {
                "id": "p",
                "date": "2026-10-25",
                "method": "Pix",
                "amountCents": 10000,
                "installmentId": "part",
            }
        ]
        new = copy.deepcopy(old)
        new["orders"][0]["installments"][0]["cancelled"] = True
        with self.assertRaises(ValueError):
            save(new, old)

    def test_layout_history_and_proof_survive_replacement(self):
        old = fixture()
        i = old["orders"][0]["items"][0]
        i.update(
            approved=True,
            image="data:image/png;base64,aGVsbG8=",
            approvalEvidence={
                "name": "Contato",
                "date": "2026-10-25",
                "channel": "WhatsApp",
                "note": "Confirmado",
            },
        )
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0].update(
            image="data:image/png;base64,bmV3", approved=False, layoutHistory=[]
        )
        clean = save(new, old)
        i = clean["orders"][0]["items"][0]
        self.assertEqual(i["layoutVersion"], 2)
        self.assertEqual(i["layoutHistory"][0]["evidence"]["name"], "Contato")
        self.assertEqual(i["approvalEvidence"], {})
        tampered = copy.deepcopy(clean)
        tampered["orders"][0]["items"][0]["layoutHistory"] = []
        self.assertEqual(len(save(tampered, clean)["orders"][0]["items"][0]["layoutHistory"]), 1)

    def test_technical_specs_roundtrip(self):
        old = fixture()
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["techniques"] = [
            {
                "type": "DTF",
                "unitCents": 0,
                "setupCents": 0,
                "specs": {
                    "width": "25",
                    "height": "30",
                    "film": "Teste",
                    "temperature": "150",
                    "seconds": "12",
                },
            }
        ]
        self.assertEqual(
            save(new, old)["orders"][0]["items"][0]["techniques"][0]["specs"]["temperature"], "150"
        )

    def test_revoking_approval_preserves_previous_proof(self):
        old = fixture()
        i = old["orders"][0]["items"][0]
        i.update(
            approved=True,
            approvalEvidence={
                "name": "Cliente teste",
                "date": "2026-10-25",
                "channel": "E-mail",
                "note": "Confirmação de teste",
            },
        )
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0].update(approved=False, approvalEvidence={})
        clean = save(new, old)
        events = clean["orders"][0]["items"][0]["approvalHistory"]
        self.assertEqual(events[0]["evidence"]["name"], "Cliente teste")
        self.assertEqual(events[0]["status"], "Aprovação retirada")
        new = copy.deepcopy(clean)
        new["orders"][0]["items"][0]["approvalHistory"] = []
        self.assertEqual(len(save(new, clean)["orders"][0]["items"][0]["approvalHistory"]), 1)


if __name__ == "__main__":
    unittest.main()
