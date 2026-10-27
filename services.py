"""Serviços em peças do cliente, separados das ordens de confecção."""

import copy
from datetime import date, datetime, timezone
import json
import re
from uuid import uuid4

import access

TECHNIQUES = ("Bordado", "DTF")
STATUSES = ("Recebido", "Em execução", "Concluído", "Entregue", "Cancelado")
UNITS = ("peça", "metro", "aplicação", "lote")
METHODS = ("Pix", "Dinheiro", "Transferência", "Cartão", "Boleto", "Outro")


def schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS service_jobs (
      id TEXT PRIMARY KEY, technique TEXT NOT NULL, number INTEGER NOT NULL,
      revision INTEGER NOT NULL, period TEXT NOT NULL, payload TEXT NOT NULL,
      UNIQUE(technique,number));
    CREATE INDEX IF NOT EXISTS service_period ON service_jobs(technique,period);
    CREATE TABLE IF NOT EXISTS service_closings (
      technique TEXT NOT NULL, month TEXT NOT NULL, revision INTEGER NOT NULL,
      payload TEXT NOT NULL, PRIMARY KEY(technique,month));
    """)


def allowed(user):
    return user["role"] in ("admin", "embroiderer")


def text(value, label, limit=3000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"Informe {label} dentro do limite de {limit} caracteres.")
    return value.strip()


def integer(value, label, maximum=100000000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{label}: use um número inteiro positivo dentro do limite.")
    return value


def month(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("Selecione o mês do fechamento.")
    date.fromisoformat(value + "-01")
    return value


def technique(value):
    if value not in TECHNIQUES:
        raise ValueError("Selecione Bordado ou DTF.")
    return value


def eligible(job):
    return job["status"] in ("Concluído", "Entregue")


def period(job):
    return (job["completedDate"] if eligible(job) else job["entryDate"])[:7]


def amounts(job):
    total = (job["qtyMilli"] * job["unitCents"] + 500) // 1000 + job["setupCents"]
    received = sum(p["amountCents"] for p in job.get("payments", []) if not p.get("voided"))
    return dict(
        totalCents=total,
        receivedCents=received,
        balanceCents=0 if job["status"] == "Cancelado" else total - received,
    )


def decorate(job):
    return dict(job, **amounts(job))


def read_job(con, jid):
    row = con.execute("SELECT payload FROM service_jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        raise ValueError("Serviço não encontrado. Atualize a lista.")
    return json.loads(row[0])


def read_closing(con, kind, selected_month):
    row = con.execute(
        "SELECT payload FROM service_closings WHERE technique=? AND month=?", (kind, selected_month)
    ).fetchone()
    return json.loads(row[0]) if row else None


def is_closed(con, kind, selected_month):
    closing = read_closing(con, kind, selected_month)
    return closing and closing["status"] == "Fechado"


def write_job(con, job):
    job["revision"] += 1
    con.execute(
        "UPDATE service_jobs SET revision=?,period=?,payload=? WHERE id=?",
        (job["revision"], period(job), json.dumps(job, ensure_ascii=False), job["id"]),
    )
    return decorate(job)


def check_revision(actual, supplied):
    if type(supplied) is not int or actual != supplied:
        raise access.Conflict("O registro mudou em outro acesso. Atualize antes de continuar.")


def save(con, data, actor, business):
    incoming = data.get("job")
    if not isinstance(incoming, dict):
        raise ValueError("Informe os dados do serviço.")
    previous = read_job(con, incoming["id"]) if incoming.get("id") else None
    kind = technique(incoming.get("technique"))
    if previous:
        check_revision(previous["revision"], data.get("revision"))
        if previous["technique"] != kind:
            raise ValueError("A técnica de um serviço existente é preservada.")
        if eligible(previous) and is_closed(con, kind, period(previous)):
            raise ValueError(
                "Este serviço pertence a um fechamento. Peça ao administrador para reabrir o mês antes de corrigir."
            )
    clients = {c["id"]: c for c in business["clients"]}
    client = clients.get(incoming.get("clientId"))
    if not client or (
        client.get("active", True) is False
        and (not previous or previous["clientId"] != client["id"])
    ):
        raise ValueError("Selecione um cliente cadastrado e ativo.")
    status = incoming.get("status", "Recebido")
    if status not in STATUSES or incoming.get("unit") not in UNITS:
        raise ValueError("Situação ou unidade do serviço inválida.")
    job = {
        key: text(incoming.get(key, ""), label, limit, required)
        for key, label, limit, required in (
            ("description", "a descrição do serviço", 500, True),
            ("seller", "a vendedora responsável", 200, False),
            ("reference", "a matriz ou referência do arquivo", 300, False),
            ("details", "os detalhes de execução", 3000, False),
            ("notes", "as observações", 3000, False),
            ("cancelReason", "o motivo do cancelamento", 1000, status == "Cancelado"),
        )
    }
    qty = integer(incoming.get("qtyMilli"), "Quantidade", 10000000)
    if qty == 0:
        raise ValueError("Informe quantidade maior que zero.")
    entry = date.fromisoformat(incoming.get("entryDate", ""))
    completed = incoming.get("completedDate", "")
    employee_id = incoming.get("employeeId", "")
    employee = next((e for e in business["employees"] if e["id"] == employee_id), None)
    if employee_id and not employee:
        raise ValueError("Responsável pelo serviço não encontrado.")
    if status in ("Em execução", "Concluído", "Entregue") and (
        not employee or employee.get("active", True) is False
    ):
        raise ValueError("Defina um funcionário ativo como responsável pela execução.")
    if status in ("Concluído", "Entregue"):
        done = date.fromisoformat(completed)
        if done < entry or done > date.today():
            raise ValueError("A conclusão deve estar entre a entrada e a data de hoje.")
    else:
        completed = ""
    job.update(
        technique=kind,
        clientId=client["id"],
        client=client["name"],
        document=client.get("document", ""),
        seller=job["seller"] or client.get("seller", ""),
        employeeId=employee_id,
        employee=employee["name"] if employee else "",
        entryDate=entry.isoformat(),
        completedDate=completed,
        status=status,
        unit=incoming["unit"],
        qtyMilli=qty,
        unitCents=integer(incoming.get("unitCents"), "Preço unitário"),
        setupCents=integer(incoming.get("setupCents", 0), "Preparação"),
        payments=copy.deepcopy(previous.get("payments", [])) if previous else [],
    )
    values = amounts(job)
    if values["receivedCents"] > values["totalCents"]:
        raise ValueError("O valor do serviço não pode ficar abaixo dos recebimentos registrados.")
    if eligible(job) and values["totalCents"] <= 0:
        raise ValueError("Informe o valor do serviço antes de concluir.")
    if status == "Cancelado" and values["receivedCents"]:
        raise ValueError("Anule os recebimentos com motivo antes de cancelar o serviço.")
    if eligible(job) and is_closed(con, kind, period(job)):
        raise ValueError(
            "O mês de conclusão está fechado. Reabra o fechamento antes de incluir ou corrigir serviços."
        )
    if previous:
        job.update(
            id=previous["id"],
            number=previous["number"],
            code=previous["code"],
            revision=previous["revision"],
            createdBy=previous["createdBy"],
        )
        result = write_job(con, job)
    else:
        number = con.execute(
            "SELECT COALESCE(MAX(number),0)+1 FROM service_jobs WHERE technique=?", (kind,)
        ).fetchone()[0]
        job.update(
            id=str(uuid4()),
            number=number,
            code=("BORD-" if kind == "Bordado" else "DTF-") + str(number).zfill(4),
            revision=1,
            createdBy={"id": actor["id"], "name": actor["name"]},
        )
        con.execute(
            "INSERT INTO service_jobs VALUES(?,?,?,?,?,?)",
            (job["id"], kind, number, 1, period(job), json.dumps(job, ensure_ascii=False)),
        )
        result = decorate(job)
    access.audit(con, actor, "Serviço avulso salvo", job["code"] + " · " + job["client"])
    return result


def receive(con, data, actor, void=False):
    job = read_job(con, data.get("id"))
    check_revision(job["revision"], data.get("revision"))
    if job["status"] == "Cancelado":
        raise ValueError("O serviço está cancelado.")
    if void:
        payment = next((p for p in job["payments"] if p["id"] == data.get("paymentId")), None)
        if not payment or payment.get("voided"):
            raise ValueError("Recebimento não encontrado ou já anulado.")
        payment.update(
            voided=True,
            voidReason=text(data.get("reason"), "o motivo da anulação", 1000, True),
            voidedBy=actor["name"],
            voidedAt=datetime.now(timezone.utc).isoformat(),
        )
    else:
        amount = integer(data.get("amountCents"), "Recebimento")
        if not 0 < amount <= amounts(job)["balanceCents"]:
            raise ValueError("O recebimento deve ser maior que zero e não superar o saldo.")
        paid = date.fromisoformat(data.get("date", ""))
        if not date.fromisoformat(job["entryDate"]) <= paid <= date.today():
            raise ValueError("A data do recebimento deve estar entre a entrada e hoje.")
        if data.get("method") not in METHODS:
            raise ValueError("Selecione a forma do recebimento.")
        job["payments"].append(
            {
                "id": str(uuid4()),
                "amountCents": amount,
                "date": paid.isoformat(),
                "method": data["method"],
                "note": text(data.get("note", ""), "a observação", 1000),
                "recordedBy": actor["name"],
                "recordedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
    result = write_job(con, job)
    access.audit(
        con,
        actor,
        "Recebimento de serviço anulado" if void else "Recebimento de serviço registrado",
        job["code"],
    )
    return result


def listing(con, kind, selected_month, business):
    kind, selected_month = technique(kind), month(selected_month)
    jobs = [
        decorate(json.loads(row[0]))
        for row in con.execute(
            "SELECT payload FROM service_jobs WHERE technique=? AND period=? ORDER BY number DESC",
            (kind, selected_month),
        )
    ]
    return {
        "jobs": jobs,
        "closing": read_closing(con, kind, selected_month),
        "company": business.get("company", {}),
    }


def close(con, data, actor, business, reopen=False):
    kind, selected_month = technique(data.get("technique")), month(data.get("month"))
    old = read_closing(con, kind, selected_month)
    check_revision(old["revision"] if old else 0, data.get("revision"))
    if reopen:
        if actor["role"] != "admin":
            raise ValueError("Somente o administrador reabre um fechamento.")
        if not old or old["status"] != "Fechado":
            raise ValueError("Não há fechamento ativo para reabrir.")
        reason = text(data.get("reason"), "o motivo da reabertura", 1000, True)
        updated = copy.deepcopy(old)
        updated.update(
            status="Reaberto",
            revision=old["revision"] + 1,
            reopened={
                "by": actor["name"],
                "at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            },
        )
    else:
        if old and old["status"] == "Fechado":
            raise ValueError("Este mês já foi fechado.")
        jobs = [j for j in listing(con, kind, selected_month, business)["jobs"] if eligible(j)]
        if not jobs:
            raise ValueError("Não há serviços concluídos neste mês para fechar.")
        groups = {}
        for job in jobs:
            group = groups.setdefault(
                job["clientId"],
                {
                    "clientId": job["clientId"],
                    "client": job["client"],
                    "document": job["document"],
                    "totalCents": 0,
                    "receivedCents": 0,
                    "balanceCents": 0,
                    "count": 0,
                },
            )
            for key in ("totalCents", "receivedCents", "balanceCents"):
                group[key] += job[key]
            group["count"] += 1
        history = copy.deepcopy(old.get("history", [])) if old else []
        if old:
            history.append({k: v for k, v in old.items() if k != "history"})
        updated = {
            "technique": kind,
            "month": selected_month,
            "status": "Fechado",
            "revision": (old["revision"] if old else 0) + 1,
            "jobs": jobs,
            "clients": list(groups.values()),
            "company": copy.deepcopy(business.get("company", {})),
            "history": history,
            "closedBy": actor["name"],
            "closedAt": datetime.now(timezone.utc).isoformat(),
            "totalCents": sum(j["totalCents"] for j in jobs),
        }
    con.execute(
        "INSERT INTO service_closings VALUES(?,?,?,?) ON CONFLICT(technique,month) DO UPDATE SET revision=excluded.revision,payload=excluded.payload",
        (kind, selected_month, updated["revision"], json.dumps(updated, ensure_ascii=False)),
    )
    access.audit(
        con,
        actor,
        "Fechamento de serviços reaberto" if reopen else "Fechamento mensal de serviços",
        f"{kind} · {selected_month}",
    )
    return updated


def export(con):
    return {
        "jobs": [
            json.loads(r[0])
            for r in con.execute("SELECT payload FROM service_jobs ORDER BY technique,number")
        ],
        "closings": [
            json.loads(r[0])
            for r in con.execute("SELECT payload FROM service_closings ORDER BY technique,month")
        ],
    }
