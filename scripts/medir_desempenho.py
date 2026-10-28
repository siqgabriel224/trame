"""Mede cenários fictícios, sem acessar o banco operacional."""

import copy
import json
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import access
from tests.test_radar import sample


def measure(action, count):
    start = time.perf_counter()
    for _ in range(count):
        action()
    return round((time.perf_counter() - start) * 1000 / count, 3)


def main():
    import base64

    data = sample()
    template = data["orders"][0]
    image = "data:image/png;base64," + base64.b64encode(bytes(range(256)) * 256).decode()
    data["orders"] = []
    for index in range(100):
        order = copy.deepcopy(template)
        order["id"] = "order-" + str(index)
        for pos, item in enumerate(order["items"]):
            item["id"] = f"item-{index}-{pos}"
            item["image"] = image
        data["orders"].append(order)
    data = server.defaults(data)
    metrics = {"orders": 100, "layouts": 200, "inline_bytes": len(json.dumps(data).encode())}
    metrics["validate_ms"] = measure(lambda: server.validate(copy.deepcopy(data), data), 3)
    original = server.DB
    try:
        with tempfile.TemporaryDirectory(dir=server.ROOT) as temporary:
            server.DB = Path(temporary) / "benchmark.sqlite3"
            server.connect().close()

            def connection():
                with closing(server.connect()):
                    pass

            metrics["connect_ms"] = measure(connection, 50)
            with closing(server.connect()) as con:
                con.execute("UPDATE state SET revision=1,payload=? WHERE id=1", (json.dumps(data),))
                con.commit()

            def uncached_read():
                with closing(server.connect()) as con:
                    revision, payload = con.execute(
                        "SELECT revision,payload FROM state WHERE id=1"
                    ).fetchone()
                return access.visible_state(
                    server.defaults(dict(json.loads(payload), revision=revision))
                )

            metrics["uncached_read_ms"] = measure(uncached_read, 3)
            server.read_state()
            metrics["cached_read_ms"] = measure(server.read_state, 10)
    finally:
        server.DB = original
    try:
        import layouts

        metrics["linked_bytes"] = len(json.dumps(layouts.compact(data)).encode())
    except ImportError:
        pass
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
