"""Regras da operação: cadastros, materiais, execução, entregas e parcelas."""

import copy
import base64
from datetime import date, datetime, timezone
from uuid import uuid4

SECTORS = [
    "Separação",
    "Corte",
    "Costura",
    "Bordado",
    "Silk",
    "DTF",
    "Acabamento",
    "Revisão",
    "Expedição",
]
TASK_STAGES = ["Pendente", "Em andamento", "Concluído"]


def sign_changes(data, old, user):
    """Registra o executor declarado e a conta que confirmou a execução."""

    def normalize_name(value):
        return " ".join(str(value).split()).casefold()

    employees = {e["id"]: e for e in data.get("employees", [])}
    previous = {
        (o["id"], i["id"], t["id"]): t
        for o in old["orders"]
        for i in o["items"]
        for t in i.get("tasks", [])
    }
    for order in data["orders"]:
        for item in order["items"]:
            for task in item.get("tasks", []):
                prior = previous.get((order["id"], item["id"], task["id"]), {})
                signature = task.get("signature")
                if prior.get("signature"):
                    if any(
                        task.get(k) != prior.get(k)
                        for k in (
                            "signature",
                            "sector",
                            "employeeId",
                            "qty",
                            "stage",
                            "completedAt",
                        )
                    ):
                        raise ValueError(
                            "A etapa assinada é preservada. Cadastre outra etapa para complemento ou correção."
                        )
                    continue
                if (
                    task.get("stage") == "Concluído"
                    and prior.get("stage") != "Concluído"
                    and not signature
                ):
                    raise ValueError("Conclua a etapa registrando a assinatura do responsável.")
                if not signature:
                    continue
                if (
                    order.get("archived")
                    or order.get("kind") == "quote"
                    or not item.get("approved")
                ):
                    raise ValueError("Assine somente etapas de uma OS ativa com layout aprovado.")
                if not isinstance(signature, dict) or signature.get("confirmed") is not True:
                    raise ValueError("Confirme a execução antes de assinar a etapa.")
                employee = employees.get(task.get("employeeId"))
                if not employee or employee.get("active", True) is False:
                    raise ValueError("Selecione um funcionário ativo para assinar a etapa.")
                if user["role"] != "admin" and user["employee_id"] != employee["id"]:
                    raise ValueError(
                        "Esta etapa deve ser assinada pelo responsável conectado ou registrada pelo administrador a partir da OS."
                    )
                if normalize_name(signature.get("name", "")) != normalize_name(employee["name"]):
                    raise ValueError(
                        "Digite o nome do funcionário responsável para confirmar a assinatura."
                    )
                signed_date = date.fromisoformat(signature.get("date", ""))
                if signed_date > date.today():
                    raise ValueError("A data da execução não pode estar no futuro.")
                if task.get("stage") != "Concluído":
                    raise ValueError("A assinatura exige etapa concluída.")
                task["completedAt"] = signed_date.isoformat()
                task["signature"] = {
                    "name": employee["name"],
                    "employeeId": employee["id"],
                    "date": signed_date.isoformat(),
                    "recordedBy": {"id": user["id"], "name": user["name"]},
                    "recordedAt": datetime.now(timezone.utc).isoformat(),
                    "source": "Registro da OS pelo administrador"
                    if user["role"] == "admin"
                    else "Responsável conectado",
                }
            prior_item = next(
                (
                    i
                    for o in old["orders"]
                    if o["id"] == order["id"]
                    for i in o["items"]
                    if i["id"] == item["id"]
                ),
                {},
            )
            if item.get("stage") in ("Pronto", "Entregue") and prior_item.get("stage") not in (
                "Pronto",
                "Entregue",
            ):
                if not item.get("tasks") or any(not t.get("signature") for t in item["tasks"]):
                    raise ValueError(
                        "Conclua e assine as etapas da OS antes de marcar o modelo como pronto."
                    )


def normalize(data):
    for key in ["clients", "employees", "stock", "reservations"]:
        data.setdefault(key, [])
    for order in data["orders"]:
        order.setdefault("installments", [])
        for item in order["items"]:
            item.setdefault("tasks", [])
            item.setdefault(
                "deliveryBaseline",
                copy.deepcopy(item["sizes"])
                if item["stage"] == "Entregue" and "deliveries" not in item
                else {},
            )
            item.setdefault("deliveries", [])
            item.setdefault("layoutHistory", [])
            item.setdefault("layoutVersion", 1)
            item.setdefault("approvalEvidence", {})
            item.setdefault("approvalHistory", [])
    return data


def identified(rows, label):
    if not isinstance(rows, list):
        raise ValueError(f"{label}: lista inválida.")
    result = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"]
            or row["id"] in result
        ):
            raise ValueError(f"{label}: identificador inválido ou repetido.")
        result[row["id"]] = row
    return result


def preserved(new, old, label):
    if not set(old).issubset(new):
        raise ValueError(
            f"{label}: preserve os registros existentes; desative, anule ou libere quando necessário."
        )


def text(entity, fields):
    for name in fields:
        if not isinstance(entity.get(name, ""), str) or len(entity.get(name, "")) > 5000:
            raise ValueError("Texto inválido ou muito longo.")


def integer(value, limit=1000000000):
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError("Informe quantidades positivas ou zero, dentro do limite.")
    return value


def delivered(item):
    result = copy.deepcopy(item.get("deliveryBaseline", {}))
    for delivery in item.get("deliveries", []):
        if not delivery.get("voided"):
            for size, qty in delivery["sizes"].items():
                result[size] = result.get(size, 0) + qty
    return result


def inventory(data, stock_id):
    stock = next(s for s in data["stock"] if s["id"] == stock_id)
    on_hand = stock["openingMilli"] + sum(
        m["qtyMilli"] * (1 if m["kind"] == "Entrada" else -1) for m in stock.get("movements", [])
    )
    reservations = [r for r in data["reservations"] if r["stockId"] == stock_id]
    on_hand -= sum(r["qtyMilli"] for r in reservations if r["stage"] == "Consumido")
    reserved = sum(r["qtyMilli"] for r in reservations if r["stage"] == "Reservado")
    return {"onHand": on_hand, "reserved": reserved, "available": on_hand - reserved}


def installment_balance(order, installment):
    return installment["amountCents"] - sum(
        p["amountCents"]
        for p in order.get("payments", [])
        if not p.get("voided") and p.get("installmentId") == installment["id"]
    )


def validate(data, old, cents, money):
    normalize(data)
    normalize(old)
    clients, old_clients = (
        identified(data["clients"], "Clientes"),
        identified(old["clients"], "Clientes"),
    )
    employees, old_employees = (
        identified(data["employees"], "Funcionários"),
        identified(old["employees"], "Funcionários"),
    )
    stocks, old_stocks = identified(data["stock"], "Estoque"), identified(old["stock"], "Estoque")
    reservations, old_reservations = (
        identified(data["reservations"], "Reservas"),
        identified(old["reservations"], "Reservas"),
    )
    for current, previous, label in [
        (clients, old_clients, "Clientes"),
        (employees, old_employees, "Funcionários"),
        (stocks, old_stocks, "Estoque"),
        (reservations, old_reservations, "Reservas"),
    ]:
        preserved(current, previous, label)
    for client in clients.values():
        if type(client.get("active", True)) is not bool:
            raise ValueError("Situação do cliente inválida.")
        text(
            client,
            [
                "name",
                "tradeName",
                "responsible",
                "document",
                "phone",
                "whatsapp",
                "email",
                "instagram",
                "website",
                "otherContact",
                "address",
                "notes",
            ],
        )
        if not client.get("name", "").strip():
            raise ValueError("Informe o nome do cliente.")
    for employee in employees.values():
        if type(employee.get("active", True)) is not bool:
            raise ValueError("Situação do funcionário inválida.")
        text(employee, ["name", "sector"])
        if not employee.get("name", "").strip() or employee.get("sector") not in SECTORS:
            raise ValueError("Informe nome e setor do funcionário.")
    for sid, stock in stocks.items():
        if type(stock.get("active", True)) is not bool:
            raise ValueError("Situação do material inválida.")
        text(stock, ["name", "unit", "notes"])
        if not stock.get("name", "").strip() or not stock.get("unit", "").strip():
            raise ValueError("Informe nome e unidade do material.")
        integer(stock["openingMilli"])
        integer(stock.get("minimumMilli", 0))
        previous = old_stocks.get(sid)
        if previous and any(stock.get(k) != previous.get(k) for k in ["openingMilli", "unit"]):
            raise ValueError(
                "Saldo inicial e unidade são preservados. Registre uma movimentação para ajustar o saldo."
            )
        movements = identified(stock.get("movements", []), "Movimentações")
        old_movements = (
            identified(previous.get("movements", []), "Movimentações") if previous else {}
        )
        preserved(movements, old_movements, "Movimentações")
        for mid, movement in movements.items():
            if mid in old_movements and movement != old_movements[mid]:
                raise ValueError(
                    "Movimentações anteriores são preservadas. Registre a movimentação inversa para corrigir."
                )
            if (
                movement.get("kind") not in ["Entrada", "Saída"]
                or integer(movement.get("qtyMilli")) == 0
            ):
                raise ValueError("Informe entrada/saída e quantidade maior que zero.")
            date.fromisoformat(movement["date"])
            text(movement, ["reason"])
            if not movement.get("reason", "").strip():
                raise ValueError("Informe o motivo da movimentação.")
    old_orders = {o["id"]: o for o in old["orders"]}
    items = {i["id"]: (o, i) for o in data["orders"] for i in o["items"]}
    for order in data["orders"]:
        prior_order = old_orders.get(order["id"])
        if order.get("clientId") and order["clientId"] not in clients:
            raise ValueError("O cliente selecionado não existe no cadastro.")
        installments = identified(order["installments"], "Parcelas")
        old_installments = (
            identified(prior_order.get("installments", []), "Parcelas") if prior_order else {}
        )
        preserved(installments, old_installments, "Parcelas")
        for part in installments.values():
            if type(part.get("cancelled", False)) is not bool:
                raise ValueError("Situação da parcela inválida.")
            if order["kind"] == "quote":
                raise ValueError("Converta o orçamento em pedido antes de programar parcelas.")
            if cents(part.get("amountCents")) == 0:
                raise ValueError("A parcela deve ser maior que zero.")
            date.fromisoformat(part["due"])
            text(part, ["label"])
            if not part.get("label", "").strip():
                raise ValueError("Identifique a parcela.")
            balance = installment_balance(order, part)
            if balance < 0 or part.get("cancelled") and balance != part["amountCents"]:
                raise ValueError("Não reduza ou cancele uma parcela abaixo do valor já recebido.")
        old_payments = {p["id"]: p for p in prior_order.get("payments", [])} if prior_order else {}
        for payment in order.get("payments", []):
            if payment["id"] in old_payments and payment.get("installmentId", "") != old_payments[
                payment["id"]
            ].get("installmentId", ""):
                raise ValueError(
                    "Preserve o vínculo dos recebimentos antigos. Anule e registre novamente para corrigir."
                )
            if payment.get("installmentId"):
                part = installments.get(payment["installmentId"])
                if not part or part.get("cancelled") and not payment.get("voided"):
                    raise ValueError("Selecione uma parcela ativa para receber.")
            elif (
                payment["id"] not in old_payments
                and not payment.get("voided")
                and any(
                    not p.get("cancelled") and installment_balance(order, p) > 0
                    for p in installments.values()
                )
            ):
                raise ValueError("Selecione a parcela deste recebimento.")
        unallocated = sum(
            p["amountCents"]
            for p in order.get("payments", [])
            if not p.get("voided") and not p.get("installmentId")
        )
        if (
            sum(p["amountCents"] for p in installments.values() if not p.get("cancelled"))
            + unallocated
            > money(order)["total"]
        ):
            raise ValueError(
                "As parcelas mais os recebimentos sem parcela não podem superar o total do pedido."
            )
        old_items = {i["id"]: i for i in prior_order["items"]} if prior_order else {}
        for item in order["items"]:
            previous = old_items.get(item["id"])
            tasks = identified(item["tasks"], "Etapas")
            old_tasks = identified(previous.get("tasks", []), "Etapas") if previous else {}
            preserved(tasks, old_tasks, "Etapas")
            for task in tasks.values():
                if task.get("sector") not in SECTORS or task.get("stage") not in TASK_STAGES:
                    raise ValueError("Setor ou andamento da etapa inválido.")
                if task.get("employeeId") and task["employeeId"] not in employees:
                    raise ValueError("Funcionário não encontrado.")
                date.fromisoformat(task["due"])
                if not 1 <= integer(task.get("qty")) <= sum(item["sizes"].values()):
                    raise ValueError(
                        "A quantidade da etapa deve estar entre 1 e o total do modelo."
                    )
                prior_task = old_tasks.get(task["id"])
                if (
                    task["stage"] != "Pendente"
                    and (not item["approved"] or order["kind"] == "quote")
                    and (not prior_task or prior_task["stage"] != task["stage"])
                ):
                    raise ValueError("A etapa só pode iniciar em pedido com layout aprovado.")
                if task["stage"] != "Pendente" and not task.get("employeeId"):
                    raise ValueError("Informe quem executa a etapa antes de iniciar ou concluir.")
                text(task, ["notes"])
            for technique in item.get("techniques", []):
                specs = technique.get("specs", {})
                if not isinstance(specs, dict):
                    raise ValueError("Ficha técnica inválida.")
                text(
                    specs,
                    [
                        "points",
                        "matrix",
                        "threads",
                        "screens",
                        "inkColors",
                        "width",
                        "height",
                        "film",
                        "temperature",
                        "seconds",
                        "pressure",
                    ],
                )
            item["deliveryBaseline"] = (
                copy.deepcopy(previous.get("deliveryBaseline", {})) if previous else {}
            )
            deliveries = identified(item["deliveries"], "Entregas")
            old_deliveries = (
                identified(previous.get("deliveries", []), "Entregas") if previous else {}
            )
            preserved(deliveries, old_deliveries, "Entregas")
            for did, delivery in deliveries.items():
                if type(delivery.get("voided", False)) is not bool:
                    raise ValueError("Situação da entrega inválida.")
                if did in old_deliveries:
                    if any(
                        delivery.get(k) != old_deliveries[did].get(k)
                        for k in ["date", "receiver", "sizes", "notes"]
                    ):
                        raise ValueError(
                            "Entregas anteriores são preservadas. Anule para corrigir."
                        )
                    if old_deliveries[did].get("voided") and delivery != old_deliveries[did]:
                        raise ValueError("Uma entrega anulada deve permanecer no histórico.")
                elif (
                    order["kind"] == "quote"
                    or not item["approved"]
                    or item["stage"] not in ["Pronto", "Entregue"]
                ):
                    raise ValueError("A entrega requer pedido com layout aprovado e modelo pronto.")
                date.fromisoformat(delivery["date"])
                text(delivery, ["receiver", "notes", "voidReason"])
                if not delivery.get("receiver", "").strip():
                    raise ValueError("Informe quem recebeu a entrega.")
                sizes = delivery.get("sizes")
                if not isinstance(sizes, dict) or not sum(
                    integer(qty, 100000) for qty in sizes.values()
                ):
                    raise ValueError("Informe quantidades para a entrega.")
                if delivery.get("voided") and not delivery.get("voidReason", "").strip():
                    raise ValueError("Informe o motivo da anulação da entrega.")
            totals = delivered(item)
            if any(
                size not in item["sizes"] or qty > item["sizes"][size]
                for size, qty in totals.items()
                if qty
            ):
                raise ValueError("A entrega não pode superar a grade de tamanhos do modelo.")
            if item["stage"] == "Entregue" and sum(totals.values()) != sum(item["sizes"].values()):
                raise ValueError("Registre a entrega de todas as peças antes de marcar Entregue.")
            # Histórico gerenciado no servidor. Alterar o cliente não apaga versões anteriores.
            history = copy.deepcopy(previous.get("layoutHistory", [])) if previous else []
            version = previous.get("layoutVersion", 1) if previous else 1
            if previous and previous.get("image", "") != item.get("image", ""):
                history.append(
                    {
                        "id": str(uuid4()),
                        "version": version,
                        "image": previous.get("image", ""),
                        "approved": previous["approved"],
                        "evidence": copy.deepcopy(previous.get("approvalEvidence", {})),
                        "replacedAt": datetime.now(timezone.utc).isoformat(),
                    }
                )
                version += 1
                item["approvalEvidence"] = {}
            item["layoutHistory"], item["layoutVersion"] = history, version
            evidence = item.get("approvalEvidence", {})
            if not isinstance(evidence, dict):
                raise ValueError("Comprovante de aprovação inválido.")
            text(evidence, ["name", "date", "channel", "note", "fileName"])
            if evidence:
                if not evidence.get("name", "").strip() or not evidence.get("date"):
                    raise ValueError("Informe quem aprovou e a data da aprovação.")
                date.fromisoformat(evidence["date"])
            if evidence.get("attachment"):
                value = evidence["attachment"]
                # O anexo é uma imagem, com limite verificado abaixo; não é executado.
                if (
                    not isinstance(value, str)
                    or len(value) > 7000000
                    or not value.startswith(
                        (
                            "data:image/png;base64,",
                            "data:image/jpeg;base64,",
                            "data:image/webp;base64,",
                        )
                    )
                ):
                    raise ValueError("O comprovante deve ser uma imagem PNG, JPEG ou WebP.")
                try:
                    base64.b64decode(value.split(",", 1)[1], validate=True)
                except Exception:
                    raise ValueError("Comprovante de aprovação inválido.")
            events = copy.deepcopy(previous.get("approvalHistory", [])) if previous else []
            old_evidence = previous.get("approvalEvidence", {}) if previous else {}
            if previous and previous["approved"] and not item["approved"] and old_evidence:
                events.append(
                    {
                        "id": str(uuid4()),
                        "version": previous.get("layoutVersion", 1),
                        "status": "Aprovação retirada",
                        "evidence": copy.deepcopy(old_evidence),
                        "recordedAt": datetime.now(timezone.utc).isoformat(),
                    }
                )
            if (
                item["approved"]
                and evidence
                and (not previous or not previous["approved"] or evidence != old_evidence)
            ):
                events.append(
                    {
                        "id": str(uuid4()),
                        "version": version,
                        "status": "Aprovado",
                        "evidence": copy.deepcopy(evidence),
                        "recordedAt": datetime.now(timezone.utc).isoformat(),
                    }
                )
            item["approvalHistory"] = events
            if not item["approved"]:
                item["approvalEvidence"] = {}
    for rid, reservation in reservations.items():
        if reservation.get("stockId") not in stocks or reservation.get("itemId") not in items:
            raise ValueError("Selecione material e modelo existentes para reservar.")
        order, item = items[reservation["itemId"]]
        if order["id"] != reservation.get("orderId") or order["kind"] == "quote":
            raise ValueError("A reserva deve estar vinculada a um modelo de pedido.")
        if integer(reservation.get("qtyMilli")) == 0 or reservation.get("stage") not in [
            "Reservado",
            "Consumido",
            "Liberado",
        ]:
            raise ValueError("Informe quantidade e situação válidas para a reserva.")
        date.fromisoformat(reservation["date"])
        text(reservation, ["note"])
        previous = old_reservations.get(rid)
        if (
            reservation["stage"] == "Consumido"
            and (not previous or previous["stage"] != "Consumido")
            and not item["approved"]
        ):
            raise ValueError("Aprove o layout antes de consumir material na produção.")
        if previous:
            if any(
                reservation.get(k) != previous.get(k)
                for k in ["stockId", "orderId", "itemId", "qtyMilli", "date", "note"]
            ):
                raise ValueError("Preserve a reserva. Libere e crie outra para corrigir.")
            if previous["stage"] != "Reservado" and reservation != previous:
                raise ValueError("Reserva consumida ou liberada permanece no histórico.")
        elif reservation["stage"] != "Reservado":
            raise ValueError("Novas reservas começam como Reservado.")
    for sid in stocks:
        values = inventory(data, sid)
        if values["onHand"] < 0 or values["available"] < 0:
            raise ValueError("Estoque insuficiente. Confira saídas, consumo e reservas ativas.")
    return data
