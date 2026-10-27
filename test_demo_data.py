import copy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from urllib.error import URLError
import os

from demo_data import build_scenario
import demonstracao
import operations
import server


class Demonstration(unittest.TestCase):
    def test_three_months_of_operations_obey_business_rules(self):
        data = build_scenario(date(2026, 10, 26))
        self.assertEqual(len(data["orders"]), 32)
        self.assertEqual(len(data["clients"]), 12)
        self.assertEqual(len(data["employees"]), 8)
        self.assertEqual(len(data["stock"]), 10)
        self.assertEqual(server.validate(copy.deepcopy(data), copy.deepcopy(data)), data)
        statuses = {server.money(o)["status"] for o in data["orders"] if o["kind"] == "order"}
        self.assertEqual(statuses, {"Pago", "Não pago", "Parcialmente pago"})
        items = [i for o in data["orders"] for i in o["items"]]
        self.assertTrue(any(i["layoutVersion"] == 2 and not i["approved"] for i in items))
        self.assertTrue(
            any(0 < sum(operations.delivered(i).values()) < sum(i["sizes"].values()) for i in items)
        )
        self.assertTrue(any(o.get("quoteSnapshot") for o in data["orders"]))
        self.assertTrue(any(p.get("voided") for o in data["orders"] for p in o["payments"]))
        self.assertTrue(
            all(operations.inventory(data, s["id"])["available"] >= 0 for s in data["stock"])
        )

    def test_demo_refuses_an_already_loaded_production_runtime(self):
        with tempfile.TemporaryDirectory(dir=server.ROOT) as folder:
            client = Mock()
            client.open.side_effect = URLError("Nenhum servidor nesta porta")
            with (
                patch.dict(os.environ),
                patch.object(demonstracao, "ROOT", Path(folder)),
                patch("sys.argv", ["demonstracao.py", "--sem-navegador"]),
                patch.object(demonstracao, "build_opener", return_value=client),
                patch.object(server, "connect") as connect,
            ):
                with self.assertRaisesRegex(RuntimeError, "outra instalação"):
                    demonstracao.main()
                connect.assert_not_called()
                self.assertFalse(list(Path(folder).rglob("*.sqlite3")))


if __name__ == "__main__":
    unittest.main()
