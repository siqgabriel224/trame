"""Limpeza pontual autorizada dos registros fictícios criados no desenvolvimento.

Não é uma rota da aplicação. Exige --apply, faz backup SQLite e preserva outros
registros. Se houver vínculo com dados reais, interrompe sem gravar.
"""

import copy
import json
import sqlite3
import sys
from datetime import datetime

DEMO_ORDERS = {
    "ff0e153c-b9a8-4569-a2b1-9c5b988027e9": "Loja Exemplo · demonstração",
    "3aaa5fe2-d26f-4182-848d-75ecdaef7623": "Oficina Exemplo · teste v2",
}
DEMO_REGISTRY = {
    "clients": {"0ff41cd0-688e-4eee-9b71-57bea279a5df": "Oficina Exemplo · teste v2"},
    "employees": {"4b99fe10-114f-4b63-8103-b87eab273951": "Pessoa Exemplo · fictício"},
    "stock": {"4a185904-e584-4aee-94da-008804d22015": "Tecido exemplo · fictício"},
}


def clean_examples(state):
    cleaned = copy.deepcopy(state)
    removed = {
        o["id"] for o in cleaned.get("orders", []) if DEMO_ORDERS.get(o["id"]) == o.get("client")
    }
    remaining = [o for o in cleaned.get("orders", []) if o["id"] not in removed]
    groups = {
        key: {r["id"] for r in cleaned.get(key, []) if ids.get(r["id"]) == r.get("name")}
        for key, ids in DEMO_REGISTRY.items()
    }
    if any(
        o.get("clientId") in groups["clients"]
        or any(
            t.get("employeeId") in groups["employees"]
            for i in o["items"]
            for t in i.get("tasks", [])
        )
        for o in remaining
    ):
        raise ValueError(
            "Um cadastro de demonstração está vinculado a pedido não fictício. Limpeza interrompida."
        )
    if any(
        r.get("stockId") in groups["stock"] and r.get("orderId") not in removed
        for r in cleaned.get("reservations", [])
    ):
        raise ValueError(
            "Material de demonstração está vinculado a outro pedido. Limpeza interrompida."
        )
    if any(
        r.get("orderId") in removed and r.get("stockId") not in groups["stock"]
        for r in cleaned.get("reservations", [])
    ):
        raise ValueError("Pedido de demonstração usa material não fictício. Limpeza interrompida.")
    counts = {"orders": len(removed)}
    cleaned["orders"] = remaining
    for key, ids in groups.items():
        cleaned[key] = [r for r in cleaned.get(key, []) if r["id"] not in ids]
        counts[key] = len(ids)
    previous = len(cleaned.get("reservations", []))
    cleaned["reservations"] = [
        r for r in cleaned.get("reservations", []) if r.get("orderId") not in removed
    ]
    counts["reservations"] = previous - len(cleaned["reservations"])
    cleaned.pop("revision", None)
    return cleaned, counts


def main():
    import server

    if "--apply" not in sys.argv:
        _, counts = clean_examples(server.read_state())
        print(json.dumps({"remover": counts}, ensure_ascii=False))
        return
    folder = server.DB.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / (
        "antes-remover-exemplos-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3"
    )
    with sqlite3.connect(server.DB) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
        revision, payload = destination.execute(
            "SELECT revision,payload FROM state WHERE id=1"
        ).fetchone()
    clean, counts = clean_examples(json.loads(payload))
    server.validate(copy.deepcopy(clean), copy.deepcopy(clean))
    with sqlite3.connect(server.DB) as con:
        updated = con.execute(
            "UPDATE state SET revision=?,payload=? WHERE id=1 AND revision=?",
            (revision + 1, json.dumps(clean, ensure_ascii=False), revision),
        )
        if updated.rowcount != 1:
            raise RuntimeError(
                "O banco mudou durante a limpeza; nenhuma alteração aplicada. Execute novamente com o servidor parado."
            )
    audit = {"removed": counts, "backup": str(backup), "revision": revision + 1}
    backup.with_suffix(".json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
