import sqlite3
import unittest
import services
import access


class ThreadColorStock(unittest.TestCase):
    def test_code_determines_swatch_independently_of_filter_group(self):
        row = services.embroidery_stock_save(
            self.con,
            {
                "item": {
                    "category": "Linha",
                    "code": "2228",
                    "color": "Vermelho",
                    "colorHex": "#ff0000",
                    "unit": "cone",
                    "openingMilli": 0,
                }
            },
            self.actor,
        )
        self.assertEqual(row["colorHex"], services.thread_color("2228")["hex"])
        self.assertEqual(row["color"], "Vermelho")
        self.assertEqual(row["colorSource"], services.thread_palette()["version"])
        self.assertNotEqual(row["colorHex"], services.thread_color("2075")["hex"])

    def test_unknown_code_does_not_infer_color_from_group(self):
        row = services.embroidery_stock_save(
            self.con,
            {
                "item": {
                    "category": "Linha",
                    "code": "999999",
                    "color": "Verde",
                    "unit": "cone",
                    "openingMilli": 0,
                }
            },
            self.actor,
        )
        self.assertEqual(row["colorHex"], "")
        self.assertEqual(row["colorSource"], "")
        self.assertIsNone(services.thread_color("999999"))

    def test_catalogue_integrity_and_explicit_aliases(self):
        palette = services.thread_palette()
        self.assertEqual(len(palette["colors"]), 286)
        self.assertEqual(services.thread_color("2228")["position"], "9N")
        self.assertEqual(services.thread_color("853")["hex"], services.thread_color("0853")["hex"])
        self.assertIsNone(services.thread_color("0028"))
        self.assertEqual(services.thread_color(" bca ")["code"], "BCA")
        import re

        self.assertTrue(
            all(re.fullmatch(r"#[0-9a-f]{6}", entry["hex"]) for entry in palette["colors"].values())
        )

    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.addCleanup(self.con.close)
        access.schema(self.con)
        services.schema(self.con)
        self.actor = {"id": "test", "name": "Teste", "role": "admin"}

    def test_simple_registration_generates_name_brand_and_keeps_swatch(self):
        row = services.embroidery_stock_save(
            self.con,
            {
                "item": {
                    "category": "Linha",
                    "color": "Verde",
                    "code": "2028",
                    "colorHex": "#4A865B",
                    "unit": "cone",
                    "openingMilli": 3000,
                    "minimumMilli": 1000,
                }
            },
            self.actor,
        )
        self.assertEqual(row["brand"], "Zenith")
        self.assertIn("2028", row["name"])
        self.assertEqual(row["colorHex"], services.thread_color("2028")["hex"])
        self.assertEqual(services.embroidery_inventory(self.con)[0]["balanceMilli"], 3000)
        self.assertEqual(
            services.export(self.con)["embroideryStock"][0]["colorHex"],
            services.thread_color("2028")["hex"],
        )

    def test_removed_fields_are_preserved_when_editing_legacy_records(self):
        row = services.embroidery_stock_save(
            self.con,
            {
                "item": {
                    "name": "Cadastro anterior",
                    "category": "Linha",
                    "color": "Verde",
                    "code": "2075",
                    "brand": "Zenith",
                    "supplier": "Fornecedor anterior",
                    "notes": "Histórico anterior",
                    "active": False,
                    "unit": "cone",
                    "openingMilli": 1000,
                }
            },
            self.actor,
        )
        edited = services.embroidery_stock_save(
            self.con,
            {
                "revision": row["revision"],
                "item": {
                    "id": row["id"],
                    "category": "Linha",
                    "color": "Verde folha",
                    "code": "2075",
                    "unit": "cone",
                    "openingMilli": 1000,
                    "minimumMilli": 2000,
                    "colorHex": "#678965",
                },
            },
            self.actor,
        )
        for field in ["name", "brand", "supplier", "notes", "active"]:
            self.assertEqual(edited[field], row[field])

    def test_invalid_swatch_cannot_be_stored(self):
        for value in ["red", "#123", "background:red", None, "#123456;display:none"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                services.embroidery_stock_save(
                    self.con,
                    {
                        "item": {
                            "category": "Linha",
                            "color": "Verde",
                            "code": "2228",
                            "colorHex": value,
                            "unit": "cone",
                            "openingMilli": 0,
                        }
                    },
                    self.actor,
                )
        self.assertEqual(self.con.execute("SELECT count(*) FROM embroidery_stock").fetchone()[0], 0)
