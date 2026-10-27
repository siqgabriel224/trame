"""Tramê local: biblioteca padrão, SQLite e consulta cadastral online opcional."""

import base64
import copy
import json
import os
import sqlite3
import socket
import threading
from contextlib import closing
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, quote
import sys
import ssl
import access
import network
import operations
from vendor.qrencoder import QRCode

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
HOME = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
CONFIG = network.configuration(HOME)
DB = Path(os.environ.get("RADAR_DB", str(HOME / "dados" / "radar.sqlite3")))
PORT = CONFIG["port"]
LOCK = threading.Lock()
STAGES = ["Aguardando", "Em produção", "Pronto", "Entregue"]
TECHNIQUES = ["Bordado", "Silk", "DTF"]
METHODS = [
    "Pix",
    "Dinheiro",
    "Cartão de crédito",
    "Cartão de débito",
    "Transferência",
    "Boleto",
    "Outro",
]


def defaults(data):
    """Migração aditiva: pedidos e bordados da primeira versão são preservados."""
    data = copy.deepcopy(data)
    data.setdefault("company", {})
    next_os = max((o.get("osNumber", 0) for o in data["orders"]), default=0)
    for o in data["orders"]:
        o.setdefault("kind", "order")
        o.setdefault("payments", [])
        o.setdefault("discountCents", 0)
        o.setdefault("freightCents", 0)
        if o["kind"] == "order" and not o.get("osNumber"):
            next_os += 1
            o["osNumber"] = next_os
        for i in o["items"]:
            i.setdefault("unitPriceCents", 0)
            i.setdefault(
                "techniques",
                [
                    {
                        "type": "Bordado",
                        "description": i.get("embroideryNotes", ""),
                        "location": "",
                        "unitCents": 0,
                        "setupCents": 0,
                    }
                ]
                if i.get("embroidery")
                else [],
            )
    return operations.normalize(data)


def item_money(item):
    qty = sum(item["sizes"].values())
    techniques = item.get("techniques", [])
    unit = item.get("unitPriceCents", 0) + sum(t.get("unitCents", 0) for t in techniques)
    setup = sum(t.get("setupCents", 0) for t in techniques)
    return qty * unit + setup


def money(order):
    subtotal = sum(item_money(i) for i in order["items"])
    total = subtotal + order.get("freightCents", 0) - order.get("discountCents", 0)
    received = sum(
        p["amountCents"] for p in order.get("payments", []) if not p.get("voided", False)
    )
    status = "Não pago" if received == 0 else "Pago" if received == total else "Parcialmente pago"
    return {
        "subtotal": subtotal,
        "total": total,
        "received": received,
        "balance": total - received,
        "status": status,
    }


def cents(value):
    if type(value) is not int or not 0 <= value <= 100000000:
        raise ValueError(
            "Valores devem ser positivos ou zero, com até duas casas decimais (limite R$ 1.000.000,00)."
        )
    return value


def text_fields(entity, fields):
    for field in fields:
        if not isinstance(entity.get(field, ""), str) or len(entity.get(field, "")) > 5000:
            raise ValueError("Campo de texto inválido ou muito longo.")


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=20)
    con.execute("PRAGMA busy_timeout=20000")
    access.schema(con)
    con.execute(
        "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)"
    )
    con.execute(
        "INSERT OR IGNORE INTO state VALUES (1, 0, ?)",
        (json.dumps({"orders": [], "warningDays": 3}),),
    )
    con.commit()
    return con


def read_state():
    with closing(connect()) as con:
        revision, payload = con.execute("SELECT revision,payload FROM state WHERE id=1").fetchone()
    return defaults(dict(json.loads(payload), revision=revision))


def validate(data, old):
    if not isinstance(data, dict) or not isinstance(data.get("orders"), list):
        raise ValueError("Dados inválidos.")
    for order in data["orders"]:
        if not isinstance(order, dict) or not isinstance(order.get("items"), list):
            raise ValueError("Pedido e lista de modelos inválidos.")
        if type(order.get("archived", False)) is not bool:
            raise ValueError("Situação de arquivamento inválida.")
        for item in order["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("sizes"), dict):
                raise ValueError("Modelo e grade inválidos.")
    days = data.get("warningDays", 3)
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError("O alerta deve ter entre 1 e 30 dias.")
    data, old = defaults(data), defaults(old)
    previous = {i["id"]: i for o in old["orders"] for i in o["items"]}
    previous_owners = {i["id"]: o["id"] for o in old["orders"] for i in o["items"]}
    old_orders = {o["id"]: o for o in old["orders"]}
    max_os = max((o.get("osNumber", 0) for o in old["orders"]), default=0)
    max_quote = max((o.get("quoteNumber", 0) for o in old["orders"]), default=0)
    company = data.get("company", {})
    if not isinstance(company, dict):
        raise ValueError("Dados da empresa inválidos.")
    text_fields(company, ["name", "tradeName", "document", "phone", "email", "address", "website"])
    seen_orders, seen_items = set(), set()
    for order in data["orders"]:
        oid = order.get("id")
        if not isinstance(oid, str) or not oid or oid in seen_orders:
            raise ValueError("Identificador de pedido inválido ou repetido.")
        seen_orders.add(oid)
        prior_order = old_orders.get(oid)
        kind = order.get("kind", "order")
        if kind not in ("order", "quote"):
            raise ValueError("Tipo de documento inválido.")
        if prior_order and prior_order["kind"] == "order" and kind != "order":
            raise ValueError("Uma OS não pode voltar a ser orçamento. Arquive se necessário.")
        # Numeração atribuída no servidor; conversão preserva o número do orçamento.
        for field in ("osNumber", "quoteNumber"):
            order.pop(field, None)
            if prior_order and prior_order.get(field):
                order[field] = prior_order[field]
        if kind == "quote" and not order.get("quoteNumber"):
            max_quote += 1
            order["quoteNumber"] = max_quote
        if kind == "order" and not order.get("osNumber"):
            max_os += 1
            order["osNumber"] = max_os
        if prior_order and prior_order["kind"] == "quote" and kind == "order":
            if not prior_order["items"]:
                raise ValueError("Adicione pelo menos um modelo antes de criar a OS.")
            if order.get("validUntil") and date.fromisoformat(order["validUntil"]) < date.today():
                raise ValueError("Revise a validade do orçamento antes de aprovar.")
            order["quoteSnapshot"] = {
                "order": copy.deepcopy(prior_order),
                "company": copy.deepcopy(company),
            }
        elif prior_order and prior_order.get("quoteSnapshot"):
            order["quoteSnapshot"] = copy.deepcopy(prior_order["quoteSnapshot"])
        else:
            order.pop("quoteSnapshot", None)
        text_fields(
            order,
            [
                "client",
                "description",
                "notes",
                "responsible",
                "seller",
                "phone",
                "whatsapp",
                "email",
                "instagram",
                "website",
                "otherContact",
                "address",
                "document",
                "paymentTerms",
                "quoteNotes",
            ],
        )
        if not str(order.get("client", "")).strip():
            raise ValueError("Informe o cliente.")
        start, due = date.fromisoformat(order["entry"]), date.fromisoformat(order["due"])
        if due < start:
            raise ValueError("O prazo não pode ser anterior à entrada.")
        if order.get("validUntil"):
            if date.fromisoformat(order["validUntil"]) < start:
                raise ValueError("A validade do orçamento não pode ser anterior à entrada.")
        cents(order.get("discountCents", 0))
        cents(order.get("freightCents", 0))
        if not isinstance(order.get("items"), list):
            raise ValueError("Lista de itens inválida.")
        for item in order["items"]:
            iid = item.get("id")
            if not isinstance(iid, str) or not iid or iid in seen_items:
                raise ValueError("Identificador de item inválido ou repetido.")
            seen_items.add(iid)
            if iid in previous_owners and previous_owners[iid] != oid:
                raise ValueError("Não é possível mover um modelo existente para outro pedido.")
            if (
                not item.get("type")
                or item.get("stage") not in STAGES
                or type(item.get("approved")) is not bool
            ):
                raise ValueError("Tipo, aprovação ou andamento inválido.")
            if kind == "quote" and item["stage"] != "Aguardando":
                raise ValueError("Converta o orçamento em pedido antes de produzir.")
            cents(item.get("unitPriceCents", 0))
            techniques = item.get("techniques", [])
            if not isinstance(techniques, list) or len(techniques) > 3:
                raise ValueError("Personalizações inválidas.")
            used = set()
            for technique in techniques:
                if (
                    not isinstance(technique, dict)
                    or technique.get("type") not in TECHNIQUES
                    or technique["type"] in used
                ):
                    raise ValueError("Selecione Bordado, Silk e/ou DTF, sem repetir a técnica.")
                used.add(technique["type"])
                cents(technique.get("unitCents", 0))
                cents(technique.get("setupCents", 0))
                text_fields(technique, ["description", "location"])
            item["embroidery"] = "Bordado" in used
            item["embroideryNotes"] = next(
                (t.get("description", "") for t in techniques if t["type"] == "Bordado"), ""
            )
            sizes = item.get("sizes")
            if (
                not isinstance(sizes, dict)
                or not sizes
                or any(type(v) is not int or v < 0 or v > 100000 for v in sizes.values())
                or sum(sizes.values()) < 1
            ):
                raise ValueError("A grade precisa ter pelo menos uma peça e quantidades inteiras.")
            image = item.get("image", "")
            if not isinstance(image, str) or len(image) > 7000000:
                raise ValueError("Imagem muito grande. Use até 5 MB.")
            if image:
                if not image.startswith(
                    ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
                ):
                    raise ValueError("Use imagens PNG, JPEG ou WebP.")
                try:
                    base64.b64decode(image.split(",", 1)[1], validate=True)
                except Exception:
                    raise ValueError("Imagem inválida.")
            prior = previous.get(iid)
            if prior is None and (item["approved"] or item["stage"] != "Aguardando"):
                raise ValueError("Novos itens devem aguardar aprovação.")
            if prior and prior.get("image", "") != image:
                if prior["stage"] != "Aguardando":
                    raise ValueError("Retorne o item para Aguardando antes de substituir o layout.")
                if item["approved"] or item["stage"] != "Aguardando":
                    raise ValueError("Um novo layout precisa de nova aprovação.")
            if not item["approved"] and item["stage"] != "Aguardando":
                raise ValueError("Aprove o layout antes de iniciar a produção.")
        payments = order.get("payments", [])
        if not isinstance(payments, list):
            raise ValueError("Pagamentos inválidos.")
        if kind == "quote" and payments:
            raise ValueError("Converta o orçamento antes de registrar recebimentos.")
        old_payments = {p["id"]: p for p in prior_order.get("payments", [])} if prior_order else {}
        payment_ids = set()
        for payment in payments:
            pid = payment.get("id")
            if not isinstance(pid, str) or not pid or pid in payment_ids:
                raise ValueError("Identificador de pagamento inválido ou repetido.")
            payment_ids.add(pid)
            if cents(payment.get("amountCents")) == 0:
                raise ValueError("Informe um recebimento maior que zero.")
            if payment.get("method") not in METHODS:
                raise ValueError("Forma de pagamento inválida.")
            date.fromisoformat(payment["date"])
            if type(payment.get("voided", False)) is not bool:
                raise ValueError("Situação do pagamento inválida.")
            text_fields(payment, ["note", "voidReason"])
            if payment.get("voided") and not payment.get("voidReason", "").strip():
                raise ValueError("Informe o motivo para anular o lançamento.")
            if pid in old_payments:
                prior_payment = old_payments[pid]
                if any(
                    payment.get(k, "") != prior_payment.get(k, "")
                    for k in ["amountCents", "date", "method", "note"]
                ):
                    raise ValueError(
                        "Recebimentos anteriores são preservados. Anule e registre novamente para corrigir."
                    )
                if prior_payment.get("voided") and payment != prior_payment:
                    raise ValueError("Um lançamento já anulado deve permanecer no histórico.")
        if not set(old_payments).issubset(payment_ids):
            raise ValueError("Anule recebimentos incorretos em vez de apagá-los.")
        totals = money(order)
        if totals["total"] < 0:
            raise ValueError("O desconto não pode superar o subtotal mais o frete.")
        if totals["received"] > totals["total"]:
            raise ValueError(
                "O recebido não pode superar o total. Confira preços, descontos e recebimentos."
            )
    # Pedidos e itens são preservados; arquivar mantém seu histórico.
    if not {o["id"] for o in old["orders"]}.issubset(seen_orders):
        raise ValueError("Arquive pedidos em vez de excluí-los.")
    if not set(previous).issubset(seen_items):
        raise ValueError("Itens existentes devem ser preservados.")
    clean = operations.validate(data, old, cents, money)
    return {
        key: clean[key]
        for key in [
            "orders",
            "warningDays",
            "company",
            "clients",
            "employees",
            "stock",
            "reservations",
        ]
    }


class TrameHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    daemon_threads = True
    tls_context = None

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(20)
        return connection, address

    def process_request_thread(self, request, address):
        # O handshake ocorre no worker: um cliente lento não trava a rede inteira.
        if self.tls_context:
            try:
                request = self.tls_context.wrap_socket(request, server_side=True)
            except (OSError, ssl.SSLError):
                request.close()
                return
        super().process_request_thread(request, address)


class Handler(network.AuthenticatedHandler, BaseHTTPRequestHandler):
    runtime = sys.modules[__name__]

    def log_message(self, *_):
        pass

    def get_business(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self.reply(200, {"status": "ok", "app": "radar-pedidos", "version": 5})
        if path == "/api/state":
            return self.reply(200, read_state())
        if path == "/domain.js":
            return self.reply(
                200, (ROOT / "web" / "domain.js").read_bytes(), "text/javascript; charset=utf-8"
            )
        if path in ["/trame.svg", "/trame.ico", "/trame.png"]:
            mime = {".svg": "image/svg+xml", ".ico": "image/x-icon", ".png": "image/png"}[
                Path(path).suffix
            ]
            return self.reply(200, (ROOT / "web" / path.lstrip("/")).read_bytes(), mime)
        if path == "/api/qr":
            oid = parse_qs(urlsplit(self.path).query).get("order", [""])[0]
            if not any(o["id"] == oid for o in read_state()["orders"]):
                return self.reply(404, {"error": "Pedido não encontrado."})
            qr = QRCode(None, 1)
            qr.addData(
                (CONFIG["public_url"] or self.authority()) + "/?order=" + quote(oid, safe="")
            )
            qr.make()
            count = qr.getModuleCount()
            rects = "".join(
                f'<rect x="{x + 4}" y="{y + 4}" width="1" height="1"/>'
                for y in range(count)
                for x in range(count)
                if qr.isDark(y, x)
            )
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {count + 8} {count + 8}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/><g fill="black">{rects}</g></svg>'
            return self.reply(200, svg.encode(), "image/svg+xml")
        files = {
            "/company.js": ("company.js", "text/javascript; charset=utf-8"),
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/commerce.js": ("commerce.js", "text/javascript; charset=utf-8"),
            "/operations.js": ("operations.js", "text/javascript; charset=utf-8"),
            "/print": ("print.html", "text/html; charset=utf-8"),
            "/print.js": ("print.js", "text/javascript; charset=utf-8"),
            "/print.css": ("print.css", "text/css; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if path in files:
            name, mime = files[path]
            return self.reply(200, (ROOT / "web" / name).read_bytes(), mime)
        self.reply(404, {"error": "Não encontrado."})


def main():
    tls = network.validate_configuration(CONFIG)
    connect().close()
    network.backup(sys.modules[__name__])
    network.bootstrap(sys.modules[__name__])
    http = TrameHTTPServer((CONFIG["bind"], PORT), Handler)
    if tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        cert, key = Path(CONFIG["cert"]), Path(CONFIG["key"])
        context.load_cert_chain(
            str(cert if cert.is_absolute() else HOME / cert),
            str(key if key.is_absolute() else HOME / key),
        )
        http.tls_context = context
    address = CONFIG["public_url"] or f"http://127.0.0.1:{PORT}"
    print("Tramê em " + address, flush=True)
    http.serve_forever()


if __name__ == "__main__":
    main()
