import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import server
import network
from test_network import Client
from remove_examples import clean_examples, DEMO_ORDERS, DEMO_REGISTRY
from test_operations import fixture


class ReviewRules(unittest.TestCase):
    def test_unallocated_balance_can_be_received_after_planned_parts_paid(self):
        old = fixture()
        o = old["orders"][0]
        o["installments"] = [
            {"id": "part", "label": "Entrada", "due": "2026-10-25", "amountCents": 10000}
        ]
        o["payments"] = [
            {
                "id": "p1",
                "amountCents": 10000,
                "date": "2026-10-25",
                "method": "Pix",
                "installmentId": "part",
            }
        ]
        new = copy.deepcopy(old)
        new["orders"][0]["payments"].append(
            {
                "id": "p2",
                "amountCents": 5000,
                "date": "2026-10-25",
                "method": "Pix",
                "installmentId": "",
            }
        )
        clean = server.validate(new, old)
        self.assertEqual(server.money(clean["orders"][0])["received"], 15000)

    def test_outstanding_part_still_requires_explicit_allocation(self):
        old = fixture()
        old["orders"][0]["installments"] = [
            {"id": "part", "label": "Entrada", "due": "2026-10-25", "amountCents": 10000}
        ]
        new = copy.deepcopy(old)
        new["orders"][0]["payments"] = [
            {"id": "p", "amountCents": 5000, "date": "2026-10-25", "method": "Pix"}
        ]
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_item_cannot_move_and_lose_its_history(self):
        old = fixture()
        new = copy.deepcopy(old)
        moved = new["orders"][0]["items"].pop(0)
        new["orders"].append(
            {
                "id": "o2",
                "client": "Outro cliente",
                "entry": "2026-10-25",
                "due": "2026-10-28",
                "items": [moved],
            }
        )
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_malformed_order_rejected_as_input_error(self):
        for orders in [[None], [{}], [{"items": [None]}], [{"items": [{"sizes": []}]}]]:
            with self.assertRaises(ValueError):
                server.validate({"orders": orders, "warningDays": 3}, {"orders": []})

    def test_delivery_cannot_hide_quantity_with_string_void_flag(self):
        old = fixture()
        old["orders"][0]["items"][0].update(approved=True, stage="Pronto")
        new = copy.deepcopy(old)
        new["orders"][0]["items"][0]["deliveries"] = [
            {
                "id": "d",
                "date": "2026-10-25",
                "receiver": "Recebedor",
                "sizes": {"P": 99},
                "voided": "false",
                "voidReason": "teste",
            }
        ]
        with self.assertRaises(ValueError):
            server.validate(new, old)

    def test_transient_revision_and_export_metadata_not_persisted(self):
        new = fixture()
        new.update(exportedAt="teste", revision=9)
        clean = server.validate(new, {"orders": []})
        self.assertNotIn("revision", clean)
        self.assertNotIn("exportedAt", clean)


class ExampleRemoval(unittest.TestCase):
    def data(self):
        data = fixture()
        data["company"] = {"name": "Minha empresa"}
        data["orders"].append(
            {"id": next(iter(DEMO_ORDERS)), "client": next(iter(DEMO_ORDERS.values())), "items": []}
        )
        for group, entries in DEMO_REGISTRY.items():
            data[group] = [{"id": i, "name": name} for i, name in entries.items()]
        data["reservations"] = []
        return data

    def test_only_known_examples_removed_and_company_preserved(self):
        data = self.data()
        clean, counts = clean_examples(data)
        self.assertEqual(counts["orders"], 1)
        self.assertEqual([o["id"] for o in clean["orders"]], ["o1"])
        self.assertEqual(clean["company"], data["company"])
        self.assertEqual(len(data["orders"]), 2)
        self.assertFalse(clean["clients"])

    def test_unknown_record_with_similar_name_preserved(self):
        data = self.data()
        data["orders"][0]["client"] = next(iter(DEMO_ORDERS.values()))
        clean, _ = clean_examples(data)
        self.assertEqual(clean["orders"][0]["id"], "o1")

    def test_real_dependency_blocks_cleanup(self):
        for field in ["client", "employee", "stock"]:
            data = self.data()
            if field == "client":
                data["orders"][0]["clientId"] = data["clients"][0]["id"]
            if field == "employee":
                data["orders"][0]["items"][0]["tasks"] = [
                    {"employeeId": data["employees"][0]["id"]}
                ]
            if field == "stock":
                data["reservations"] = [{"orderId": "o1", "stockId": data["stock"][0]["id"]}]
            with self.assertRaises(ValueError):
                clean_examples(data)

    def test_cleanup_can_be_repeated_without_removing_real_records(self):
        data = self.data()
        first, _ = clean_examples(data)
        second, counts = clean_examples(first)
        self.assertEqual(first, second)
        self.assertEqual(sum(counts.values()), 0)


class HTTPReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=server.ROOT)
        self.previous = server.DB
        server.DB = Path(self.temp.name) / "isolated.sqlite3"
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.http.server_port}"
        network.bootstrap(server)
        self.client = Client(self.url)
        token = (server.DB.parent / "chave-primeiro-acesso.txt").read_text()
        self.client.request(
            "/api/setup",
            {
                "token": token,
                "name": "Teste",
                "username": "admin",
                "password": "senha-teste-revisao",
            },
        )
        self.client.login("admin", "senha-teste-revisao")

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DB = self.previous
        self.temp.cleanup()

    def request(self, path, data=None, origin=None):
        status, body, _ = self.client.request(path, data, origin or True)
        return status, json.dumps(body).encode() if isinstance(body, (dict, list)) else body

    def test_static_domain_icon_and_blank_start(self):
        for path in ["/", "/domain.js", "/trame.ico"]:
            status, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
        _, body = self.request("/api/state")
        self.assertEqual(json.loads(body)["orders"], [])

    def test_invalid_input_is_400_and_does_not_change_state(self):
        status, _ = self.request("/api/state", {"revision": 0, "orders": [None], "warningDays": 3})
        self.assertEqual(status, 400)
        _, body = self.request("/api/state")
        self.assertEqual(json.loads(body)["revision"], 0)

    def test_authenticated_completion_stamps_and_preserves_signature(self):
        from test_operations import Operations

        data = Operations().task_fixture()
        data["revision"] = 0
        status, body = self.request("/api/state", data)
        self.assertEqual(status, 200)
        current = json.loads(body)
        candidate = copy.deepcopy(current)
        item = candidate["orders"][0]["items"][0]
        item["approved"] = True
        item["tasks"][0]["stage"] = "Concluído"
        self.assertEqual(self.request("/api/state", candidate)[0], 400)
        item["tasks"][0]["signature"] = {
            "name": "Pessoa teste",
            "date": "2026-10-20",
            "confirmed": True,
            "recordedBy": {"name": "Inventado"},
        }
        status, body = self.request("/api/state", candidate)
        self.assertEqual(status, 200)
        signed = json.loads(body)
        task = signed["orders"][0]["items"][0]["tasks"][0]
        self.assertEqual(task["signature"]["recordedBy"]["name"], "Teste")
        self.assertEqual(task["completedAt"], "2026-10-20")
        task["signature"]["name"] = "Troca"
        self.assertEqual(self.request("/api/state", signed)[0], 400)

    def test_save_conflict_and_origin_protection(self):
        data = fixture()
        data["revision"] = 0
        status, body = self.request("/api/state", data)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["revision"], 1)
        self.assertEqual(self.request("/api/state", data)[0], 409)
        data["revision"] = 1
        self.assertEqual(self.request("/api/state", data, "https://outro.example")[0], 403)


if __name__ == "__main__":
    unittest.main()
