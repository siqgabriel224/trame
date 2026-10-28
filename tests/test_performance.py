"""Regressões do transporte de layouts, conflitos e inicialização de schema."""

import copy
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
from unittest.mock import patch

import access
import layouts
import server
from tests import test_network
from tests.test_radar import sample

IMAGE = "data:image/png;base64,bGF5b3V0"


class SchemaConnections(unittest.TestCase):
    def test_read_cache_does_not_leak_edits_or_hide_external_same_revision_write(self):
        original = server.DB
        try:
            with tempfile.TemporaryDirectory(dir=server.ROOT) as folder:
                server.DB = Path(folder) / "cache.sqlite3"
                first = server.read_state()
                first["warningDays"] = 90
                self.assertEqual(server.read_state()["warningDays"], 3)
                # Imports/maintenance can replace payload without changing revision.
                with closing(server.connect()) as con:
                    con.execute(
                        "UPDATE state SET payload=? WHERE id=1",
                        (json.dumps({"orders": [], "warningDays": 7}),),
                    )
                    con.commit()
                self.assertEqual(server.read_state()["warningDays"], 7)
        finally:
            server.DB = original

    def test_migrations_are_reused_and_detect_schema_or_file_replacement(self):
        original = server.DB
        try:
            with tempfile.TemporaryDirectory(dir=server.ROOT) as folder:
                server.DB = Path(folder) / "schema.sqlite3"
                with patch.object(access, "schema", wraps=access.schema) as initialize:
                    server.connect().close()
                    server.connect().close()
                    self.assertEqual(initialize.call_count, 1)
                    with closing(server.connect()) as con:
                        con.execute("CREATE TABLE extra(value TEXT)")
                        con.commit()
                    server.connect().close()
                    self.assertEqual(initialize.call_count, 2)
                    server.DB.unlink()
                    with closing(server.connect()) as con:
                        self.assertEqual(con.execute("SELECT count(*) FROM state").fetchone()[0], 1)
                    self.assertEqual(initialize.call_count, 3)
        finally:
            server.DB = original


class LayoutTransport(unittest.TestCase):
    def test_compact_roundtrip_including_historical_quote(self):
        state = sample()
        state["orders"][0]["items"][0]["image"] = IMAGE
        order = state["orders"][0]
        order["quoteSnapshot"] = {"order": copy.deepcopy(order), "company": {}}
        linked = layouts.compact(state)
        self.assertNotIn("data:image", json.dumps(linked))
        self.assertEqual(order["items"][0]["image"], IMAGE)
        historical = linked["orders"][0]["quoteSnapshot"]["order"]["items"][0]["image"]
        self.assertIn("snapshot=quote", historical)
        layouts.restore_submission(linked, state)
        self.assertEqual(linked, state)

    def test_link_is_bound_to_order_item_content_and_scope(self):
        state = sample()
        state["orders"][0]["items"][0]["image"] = IMAGE
        link = layouts.compact(state)["orders"][0]["items"][0]["image"]
        from urllib.parse import parse_qs, urlsplit

        params = parse_qs(urlsplit(link).query)
        digest = params["v"][0]
        self.assertEqual(layouts.read(state, "o1", "i1", digest), ("image/png", b"layout"))
        self.assertIsNone(layouts.read(state, "o1", "i2", digest))
        self.assertIsNone(layouts.read(state, "other", "i1", digest))
        self.assertIsNone(layouts.read(state, "o1", "i1", digest, "quote"))
        state["orders"][0]["items"][0]["image"] = "data:image/png;base64,bmV3"
        self.assertIsNone(layouts.read(state, "o1", "i1", digest))


class LayoutHTTP(unittest.TestCase):
    def setUp(self):
        self.fixture = test_network.NetworkFlow()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        state = self.fixture.state()
        state["orders"] = sample()["orders"]
        state["orders"][0]["items"][0]["image"] = IMAGE
        self.assertEqual(self.fixture.client.request("/api/state", state)[0], 200)

    def linked(self, path="/api/state", data=None, client=None):
        client = client or self.fixture.client
        headers = {"X-Trame-Layouts": "links"}
        if data is not None:
            headers.update(
                {
                    "Content-Type": "application/json",
                    "Origin": client.url,
                    "X-CSRF-Token": client.csrf,
                }
            )
        request = Request(
            client.url + path, json.dumps(data).encode() if data is not None else None, headers
        )
        try:
            response = client.opener.open(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            if response.headers.get_content_type() == "application/json":
                body = json.loads(body)
            return response.status, body

    def test_authenticated_lazy_image_and_legacy_export(self):
        status, state = self.linked()
        self.assertEqual(status, 200)
        self.assertNotIn("data:image", json.dumps(state))
        link = state["orders"][0]["items"][0]["image"]
        with patch.object(
            server.json,
            "loads",
            side_effect=AssertionError("O layout não deve reprocessar o histórico"),
        ):
            self.assertEqual(self.linked(link), (200, b"layout"))
        anonymous = test_network.Client(self.fixture.url)
        self.assertEqual(self.linked(link, client=anonymous)[0], 401)
        self.assertEqual(
            self.fixture.client.request("/api/state")[1]["orders"][0]["items"][0]["image"], IMAGE
        )
        self.assertEqual(
            self.fixture.client.request("/api/export")[1]["orders"][0]["items"][0]["image"], IMAGE
        )

    def test_save_keeps_image_and_approval_and_conflicts_for_stale_form(self):
        _, state = self.linked()
        before = state["orders"][0]
        after = copy.deepcopy(before)
        after["notes"] = "Revisado"
        payload = {
            "changes": [{"key": "orders", "id": before["id"], "before": before, "after": after}]
        }
        status, saved = self.linked("/api/changes", payload)
        self.assertEqual(status, 200)
        self.assertEqual(saved["orders"][0]["items"][0]["image"], before["items"][0]["image"])
        self.assertEqual(self.fixture.state()["orders"][0]["items"][0]["image"], IMAGE)
        self.assertEqual(self.linked("/api/changes", payload)[0], 409)

    def test_stale_image_reference_and_invalid_new_upload_do_not_save(self):
        _, state = self.linked()
        before = state["orders"][0]
        after = copy.deepcopy(before)
        after["items"][0]["image"] = before["items"][0]["image"][:-1] + "x"
        payload = {
            "changes": [{"key": "orders", "id": before["id"], "before": before, "after": after}]
        }
        self.assertEqual(self.linked("/api/changes", payload)[0], 409)
        after["items"][0]["image"] = "data:image/png;base64,!"
        self.assertEqual(self.linked("/api/changes", payload)[0], 400)
        self.assertEqual(self.fixture.state()["orders"][0]["items"][0]["image"], IMAGE)

    def test_historical_layout_survives_current_layout_replacement(self):
        # Seed a valid quote, convert it through the actual API, then replace the OS layout.
        # Existing records cannot be removed: use a second independent quote instead.
        quote = copy.deepcopy(sample()["orders"][0])
        quote["id"] = "quote-2"
        quote["kind"] = "quote"
        for item in quote["items"]:
            item["id"] += "-quote"
        quote["items"][0]["image"] = IMAGE
        status, saved, _ = self.fixture.change("orders", quote["id"], None, quote)
        self.assertEqual(status, 200)
        before = next(o for o in saved["orders"] if o["id"] == quote["id"])
        after = copy.deepcopy(before)
        after["kind"] = "order"
        status, saved, _ = self.fixture.change("orders", before["id"], before, after)
        self.assertEqual(status, 200)
        before = next(o for o in saved["orders"] if o["id"] == quote["id"])
        after = copy.deepcopy(before)
        after["items"][0]["image"] = "data:image/png;base64,bmV3"
        self.assertEqual(self.fixture.change("orders", before["id"], before, after)[0], 200)
        _, state = self.linked()
        linked = next(o for o in state["orders"] if o["id"] == quote["id"])
        current = linked["items"][0]["image"]
        historical = linked["quoteSnapshot"]["order"]["items"][0]["image"]
        self.assertEqual(self.linked(current), (200, b"new"))
        self.assertEqual(self.linked(historical), (200, b"layout"))
        linked["notes"] = "Histórico preservado"
        self.assertEqual(self.linked("/api/state", state)[0], 200)
