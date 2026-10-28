import unittest
from datetime import date, timedelta
import test_services


class ServiceLines(unittest.TestCase):
    setUp = test_services.ServiceHTTP.setUp
    tearDown = test_services.ServiceHTTP.tearDown
    registries = test_services.ServiceHTTP.registries

    def payload(self):
        today = date.today().isoformat()
        return dict(
            technique="Bordado",
            clientId="c",
            entryDate=today,
            dueDate=today,
            status="Em andamento",
            lines=[
                dict(description="Frente", qtyMilli=10000, unitCents=250),
                dict(description="Costas", qtyMilli=10000, unitCents=500),
                dict(description="Manga", qtyMilli=10000, unitCents=125),
            ],
        )

    def test_multiple_positions_totals_completion_and_closing(self):
        self.registries()
        row = self.payload()
        status, saved, _ = self.client.request("/api/services/save", dict(job=row))
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["totalCents"], 8750)
        self.assertEqual(len(saved["lines"]), 3)
        self.assertEqual(saved["completedDate"], "")
        row = dict(saved, status="Concluído")
        status, done, _ = self.client.request(
            "/api/services/save", dict(job=row, revision=saved["revision"])
        )
        self.assertEqual(status, 200, done)
        self.assertEqual(done["completedDate"], date.today().isoformat())
        self.assertEqual(done["employeeId"], "")
        self.assertEqual(
            self.client.request(
                "/api/services/close",
                dict(technique="Bordado", month=date.today().strftime("%Y-%m"), revision=0),
            )[0],
            200,
        )
        self.assertEqual(
            self.client.request("/api/services/save", dict(job=done, revision=done["revision"]))[0],
            400,
        )

    def test_dates_quantities_and_missing_lines_rejected(self):
        self.registries()
        row = self.payload()
        row["dueDate"] = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(self.client.request("/api/services/save", dict(job=row))[0], 400)
        for lines in (
            [],
            [dict(description="", qtyMilli=1000, unitCents=100)],
            [dict(description="Frente", qtyMilli=0, unitCents=100)],
            [dict(description="Frente", qtyMilli=1000, unitCents=-1)],
        ):
            row = self.payload()
            row["lines"] = lines
            self.assertEqual(self.client.request("/api/services/save", dict(job=row))[0], 400)
        _, saved, _ = self.client.request("/api/services/save", dict(job=self.payload()))
        del saved["lines"]
        self.assertEqual(
            self.client.request("/api/services/save", dict(job=saved, revision=saved["revision"]))[
                0
            ],
            400,
        )
