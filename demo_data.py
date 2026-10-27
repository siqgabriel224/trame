"""Cenário fictício de três meses, construído pelas regras reais do Tramê."""

import base64
import copy
from datetime import timedelta
import struct
import zlib

CLIENTS = [
    "Ateliê Aurora",
    "Café Horizonte",
    "Escola Sementes",
    "Mercado do Bairro",
    "Estúdio Norte",
    "Clínica Bem Viver",
    "Hotel Brisa",
    "Equipe Montanha",
    "Padaria do Largo",
    "Oficina Ponto Certo",
    "Festival Raízes",
    "Associação Vila Nova",
]
EMPLOYEES = [
    ("Lia Martins", "Corte"),
    ("Rafaela Costa", "Costura"),
    ("João Alves", "Bordado"),
    ("Bia Santos", "Silk"),
    ("Davi Lima", "DTF"),
    ("Clara Rocha", "Acabamento"),
    ("Nina Oliveira", "Expedição"),
    ("Pedro Dias", "Revisão"),
]


def layout_image(color):
    """Desenho técnico simples da peça, em PNG gerado sem dependências."""
    size = 160
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            body = 42 <= x <= 118 and 40 <= y <= 140
            sleeves = 24 <= y <= 61 and 20 <= x <= 140 and abs(x - 80) <= 62 - (y - 24) // 3
            neck = 65 <= x <= 95 and 23 <= y <= 41
            mark = 63 <= x <= 98 and 63 <= y <= 79
            pixel = (
                (247, 249, 242)
                if not (body or sleeves) or neck
                else ((226, 238, 191) if mark else color)
            )
            row.extend(pixel)
        rows.append(bytes(row))

    def chunk(kind, value):
        return (
            struct.pack("!I", len(value))
            + kind
            + value
            + struct.pack("!I", zlib.crc32(kind + value) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


def build_scenario(anchor):
    import server

    state = server.defaults({"orders": [], "warningDays": 5})

    def day(offset):
        return (anchor + timedelta(days=offset)).isoformat()

    def apply(change):
        nonlocal state
        candidate = copy.deepcopy(state)
        change(candidate)
        state = server.validate(candidate, copy.deepcopy(state))

    def order(data, oid):
        return next(row for row in data["orders"] if row["id"] == oid)

    colors = [(41, 83, 65), (67, 92, 124), (179, 129, 87), (112, 115, 78)]
    images = [layout_image(color) for color in colors]
    company = {
        "name": "Fio & Forma Confecção · empresa fictícia",
        "tradeName": "Fio & Forma",
        "document": "00.000.000/0000-00",
        "phone": "(11) 0000-0000",
        "email": "contato@example.com",
        "website": "https://example.com",
        "address": "Rua dos Exemplos, 120 · Cidade Exemplo · Dados de demonstração",
    }

    def registries(data):
        data["company"] = company
        data["clients"] = [
            {
                "id": f"c-{i}",
                "name": name,
                "tradeName": name,
                "responsible": f"Contato fictício {i + 1}",
                "document": "",
                "phone": "(11) 0000-0000",
                "whatsapp": "",
                "email": f"cliente{i + 1}@example.com",
                "address": f"Rua de Demonstração, {100 + i} · Cidade Exemplo",
                "active": True,
                "notes": "Cliente fictício para explorar o sistema.",
            }
            for i, name in enumerate(CLIENTS)
        ]
        data["employees"] = [
            {"id": f"e-{i}", "name": name, "sector": sector, "active": True}
            for i, (name, sector) in enumerate(EMPLOYEES)
        ]
        names = [
            "Malha algodão areia",
            "Malha verde oliva",
            "Moletom azul marinho",
            "Linha branca",
            "Linha dourada",
            "Filme DTF",
            "Tinta silk preta",
            "Bobinas de linha verde",
            "Embalagens individuais",
            "Etiquetas personalizadas",
        ]
        data["stock"] = [
            {
                "id": f"s-{i}",
                "name": name,
                "unit": "m" if i < 3 else "un",
                "openingMilli": 1000000 if i < 3 else (0 if i == 9 else 120000),
                "minimumMilli": 100000 if i < 3 else 150000 if i == 7 else 20000,
                "movements": [
                    {
                        "id": f"m-{i}-1",
                        "kind": "Entrada",
                        "qtyMilli": 250000 if i < 3 else 25000,
                        "date": day(-35),
                        "reason": "Reposição de demonstração",
                    }
                ]
                if i != 9
                else [],
                "active": True,
                "notes": "Material fictício.",
            }
            for i, name in enumerate(names)
        ]

    apply(registries)
    descriptions = [
        "Uniformes da equipe",
        "Camisetas para evento",
        "Coleção de primavera",
        "Reposição de uniformes",
        "Linha promocional",
        "Jaquetas de atendimento",
    ]

    def make_order(i, quote=False):
        ci = i % len(CLIENTS)
        entry = (
            -84 + i * 4 if i < 15 and not quote else -14 + (i - 15) if not quote else -24 + i * 2
        )
        due = (
            entry + 10
            if i < 15 and not quote
            else [-3, -2, 2, 4, 0, 3, 7, 10, 1][i - 15]
            if not quote
            else 12 + i
        )
        oid = f"q-{i}" if quote else f"o-{i}"
        items = []
        for j in range(2 if i % 4 == 0 else 1):
            technique = ["Bordado", "Silk", "DTF"][(i + j) % 3]
            sizes = (
                {"P": 6 + i % 4, "M": 12 + i % 5, "G": 10, "GG": 4} if j == 0 else {"M": 5, "G": 5}
            )
            itemid = f"{oid}-i-{j}"
            employee = {"Bordado": 2, "Silk": 3, "DTF": 4}[technique]
            items.append(
                {
                    "id": itemid,
                    "type": "Camiseta" if j == 0 else "Jaqueta",
                    "description": descriptions[i % 6],
                    "fabric": "Algodão 100%" if j == 0 else "Moletom",
                    "color": ["Areia", "Verde oliva", "Azul marinho", "Terracota"][i % 4],
                    "sizes": sizes,
                    "image": images[i % 4],
                    "approved": False,
                    "stage": "Aguardando",
                    "unitPriceCents": 2790 + i * 70 if j == 0 else 8900,
                    "techniques": [
                        {
                            "type": technique,
                            "description": "Marca no peito · arquivo de demonstração",
                            "location": "Peito esquerdo",
                            "unitCents": 590,
                            "setupCents": 4500,
                        }
                    ],
                    "tasks": []
                    if quote
                    else [
                        {
                            "id": f"{itemid}-t-{n}",
                            "sector": sector,
                            "employeeId": f"e-{worker}",
                            "qty": sum(sizes.values()),
                            "due": day(due - 1),
                            "stage": "Pendente",
                            "notes": "Etapa fictícia de produção.",
                        }
                        for n, (sector, worker) in enumerate(
                            [("Costura", 1), (technique, employee), ("Acabamento", 5)]
                        )
                    ],
                }
            )
        return {
            "id": oid,
            "kind": "quote" if quote else "order",
            "clientId": f"c-{ci}",
            "client": CLIENTS[ci],
            "description": descriptions[i % 6] + (" · orçamento" if quote else ""),
            "entry": day(entry),
            "due": day(due),
            "validUntil": day(-4 if i < 2 else 7 + i) if quote else "",
            "responsible": f"Contato fictício {ci + 1}",
            "seller": "Equipe Fio & Forma",
            "phone": "(11) 0000-0000",
            "email": f"cliente{ci + 1}@example.com",
            "address": f"Rua de Demonstração, {100 + ci}",
            "notes": "Dados fictícios. Você pode editar e acompanhar as mudanças nesta demonstração.",
            "paymentTerms": "40% na entrada e 60% na entrega",
            "items": items,
            "archived": False,
            "payments": [],
            "discountCents": 0,
            "freightCents": 1500 if i % 3 == 0 else 0,
        }

    apply(
        lambda d: d["orders"].extend(
            [make_order(i) for i in range(24)] + [make_order(i, True) for i in range(8)]
        )
    )

    def convert(data):
        for i in range(5, 8):
            order(data, f"q-{i}")["kind"] = "order"

    apply(convert)

    def approve(data):
        for i in range(24):
            if i in [16, 21]:
                continue
            for item in order(data, f"o-{i}")["items"]:
                item["approved"] = True
                item["approvalEvidence"] = {
                    "name": f"Contato fictício {i % 12 + 1}",
                    "date": order(data, f"o-{i}")["entry"],
                    "channel": "WhatsApp",
                    "note": "Aprovação fictícia do layout apresentado.",
                }

    apply(approve)

    def production(data):
        for i in range(24):
            current = order(data, f"o-{i}")
            for j, item in enumerate(current["items"]):
                if i not in [16, 21, 22]:
                    item["stage"] = "Pronto" if i < 15 or i in [19, 20, 23] else "Em produção"
                    for n, task in enumerate(item["tasks"]):
                        task["stage"] = (
                            "Concluído"
                            if item["stage"] == "Pronto" or n == 0
                            else "Em andamento"
                            if n == 1
                            else "Pendente"
                        )
                        if task["stage"] == "Concluído":
                            task["completedAt"] = current["entry"]
                data["reservations"].append(
                    {
                        "id": f"r-{i}-{j}",
                        "stockId": f"s-{i % 3}",
                        "orderId": current["id"],
                        "itemId": item["id"],
                        "qtyMilli": sum(item["sizes"].values()) * 1200,
                        "stage": "Reservado",
                        "date": current["entry"],
                        "note": "Material reservado para este modelo.",
                    }
                )

    apply(production)

    def logistics(data):
        for i in range(24):
            current = order(data, f"o-{i}")
            for item in current["items"]:
                if i < 15 or i == 20:
                    sizes = (
                        copy.deepcopy(item["sizes"])
                        if i < 15
                        else {size: max(0, qty // 2) for size, qty in item["sizes"].items()}
                    )
                    item["deliveries"].append(
                        {
                            "id": f"{item['id']}-delivery",
                            "date": current["due"] if i < 15 else day(-1),
                            "receiver": current["responsible"],
                            "sizes": sizes,
                            "notes": "Entrega fictícia completa."
                            if i < 15
                            else "Primeira remessa. Saldo aguardando retirada.",
                        }
                    )
                    if i < 15:
                        item["stage"] = "Entregue"
            if i < 3:
                current["archived"] = True
        for reservation in data["reservations"]:
            index = int(reservation["orderId"].split("-")[1])
            if index not in [16, 21, 22]:
                reservation["stage"] = "Consumido"
        revised = order(data, "o-22")["items"][0]
        revised.update(approved=False, image=images[1], stage="Aguardando")

    apply(logistics)

    def installments(data):
        for current in data["orders"]:
            if current["kind"] == "quote":
                continue
            value = server.money(current)["total"]
            entry = value * 40 // 100
            current["installments"] = [
                {
                    "id": current["id"] + "-p1",
                    "label": "Entrada · 40%",
                    "due": current["entry"],
                    "amountCents": entry,
                },
                {
                    "id": current["id"] + "-p2",
                    "label": "Saldo · entrega",
                    "due": current["due"],
                    "amountCents": value - entry,
                },
            ]

    apply(installments)

    def payments(data):
        for i in range(24):
            current = order(data, f"o-{i}")
            if i in [14, 16, 21, 22]:
                continue
            for n, part in enumerate(current["installments"]):
                if n == 1 and i >= 12:
                    continue
                current["payments"].append(
                    {
                        "id": part["id"] + "-receipt",
                        "installmentId": part["id"],
                        "amountCents": part["amountCents"],
                        "date": part["due"],
                        "method": "Pix" if n == 0 else "Transferência",
                        "note": "Recebimento fictício conciliado.",
                    }
                )

    apply(payments)

    def mistake(data):
        current = order(data, "o-13")
        current["payments"].append(
            {
                "id": "receipt-corrected",
                "installmentId": current["installments"][1]["id"],
                "amountCents": 1000,
                "date": day(-8),
                "method": "Dinheiro",
                "note": "Exemplo de lançamento posteriormente corrigido.",
            }
        )

    apply(mistake)

    def void(data):
        entry = next(p for p in order(data, "o-13")["payments"] if p["id"] == "receipt-corrected")
        entry.update(
            voided=True,
            voidReason="Valor lançado por engano. Registro preservado para conferência.",
        )

    apply(void)
    return state
