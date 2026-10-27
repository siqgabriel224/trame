"""Consulta opcional de dados públicos de empresas pela BrasilAPI."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://brasilapi.com.br/api/cnpj/v1/"
MAX_RESPONSE = 262144


class LookupError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def normalize(value):
    if not isinstance(value, str) or len(value) > 30:
        raise ValueError(
            "Informe um CNPJ completo para consultar. CPF não possui consulta automática."
        )
    document = re.sub(r"[./\s-]", "", value).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", document) or len(set(document)) == 1:
        raise ValueError(
            "Informe um CNPJ válido com 14 posições, incluindo os dois dígitos finais."
        )
    return document


def formatted(document):
    return f"{document[:2]}.{document[2:5]}.{document[5:8]}/{document[8:12]}-{document[12:]}"


def company_fields(payload, expected):
    if not isinstance(payload, dict):
        raise LookupError("A consulta retornou dados incompletos. Tente novamente mais tarde.")

    def text(key, limit=200):
        value = payload.get(key)
        return value.strip()[:limit] if isinstance(value, str) else ""

    try:
        matches = normalize(payload.get("cnpj")) == expected
    except ValueError:
        matches = False
    if not matches or not text("razao_social"):
        raise LookupError(
            "A fonte não confirmou os dados deste CNPJ. Preencha manualmente ou tente depois."
        )
    street = " ".join(filter(None, [text("descricao_tipo_de_logradouro"), text("logradouro")]))
    number = text("numero")
    if street.rsplit(" ", 1)[-1].casefold() == number.casefold():
        number = ""
    city = " / ".join(filter(None, [text("municipio"), text("uf")]))
    postal = text("cep").replace("-", "")
    if len(postal) == 8 and postal.isdigit():
        postal = postal[:5] + "-" + postal[5:]
    address = ", ".join(
        filter(
            None,
            [
                street,
                number,
                text("complemento"),
                text("bairro"),
                city,
                "CEP " + postal if postal else "",
            ],
        )
    )
    phone = text("ddd_telefone_1", 60) or text("ddd_telefone_2", 60)
    if phone.isdigit() and len(phone) in (10, 11):
        phone = f"({phone[:2]}) {phone[2:-4]}-{phone[-4:]}"
    email = text("email")
    return {
        "company": {
            "name": text("razao_social"),
            "tradeName": text("nome_fantasia"),
            "document": formatted(expected),
            "phone": phone,
            "email": email if "@" in email else "",
            "address": address[:1000],
        },
        "status": text("descricao_situacao_cadastral", 60),
        "source": "BrasilAPI",
    }


def lookup(value):
    document = normalize(value)
    request = Request(
        API + document, headers={"Accept": "application/json", "User-Agent": "Trame/1.0"}
    )
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise LookupError(
                "A resposta da consulta excedeu o limite. Preencha os dados manualmente."
            )
        payload = json.loads(raw)
    except HTTPError as exc:
        status = exc.code
        exc.close()
        if status == 404:
            raise LookupError(
                "CNPJ não encontrado na fonte consultada. Confira o número.", 404
            ) from exc
        if status == 400:
            raise LookupError(
                "A fonte recusou este CNPJ. Confira os dados digitados.", 400
            ) from exc
        raise LookupError(
            "A consulta está indisponível ou atingiu o limite. Tente novamente mais tarde."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise LookupError(
            "Não foi possível consultar. Confira a conexão com a internet ou preencha manualmente."
        ) from exc
    except (ValueError, UnicodeError) as exc:
        raise LookupError(
            "A fonte retornou uma resposta inválida. Tente novamente mais tarde."
        ) from exc
    return company_fields(payload, document)
