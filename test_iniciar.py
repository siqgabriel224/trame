"""Falhas de inicialização não devem criar nem alterar dados."""

import contextlib
import io
import os
import unittest
from unittest.mock import patch
import iniciar
import server


class Startup(unittest.TestCase):
    def test_two_servers_cannot_share_the_same_port(self):
        with server.TrameHTTPServer(("127.0.0.1", 0), server.Handler) as first:
            with self.assertRaises(OSError):
                server.TrameHTTPServer(("127.0.0.1", first.server_port), server.Handler)

    def test_busy_port_does_not_touch_database_or_open_browser(self):
        with (
            patch.dict(os.environ),
            patch("sys.argv", ["iniciar.py", "--porta", "18749"]),
            patch.object(server, "TrameHTTPServer", side_effect=OSError("Porta ocupada")),
            patch.object(server, "connect") as connect,
            patch.object(iniciar.webbrowser, "open") as browser,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as error:
                iniciar.main()
            self.assertEqual(error.exception.code, 1)
            connect.assert_not_called()
            browser.assert_not_called()

    def test_invalid_port_is_rejected_before_server_starts(self):
        for port in ["80", "65536", "-1"]:
            with (
                patch("sys.argv", ["iniciar.py", "--porta", port]),
                patch.object(server, "TrameHTTPServer") as http,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    iniciar.main()
                self.assertEqual(error.exception.code, 2)
                http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
