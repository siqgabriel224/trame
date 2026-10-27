import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import cnpj
from test_network import Client
import test_network

DOCUMENT = "19131243000197"
PUBLIC = {
    "cnpj": DOCUMENT,
    "razao_social": "OFICINA EXEMPLO LTDA",
    "nome_fantasia": "Oficina Exemplo",
    "descricao_tipo_de_logradouro": "RUA",
    "logradouro": "DAS FLORES",
    "numero": "100",
    "bairro": "CENTRO",
    "municipio": "SAO PAULO",
    "uf": "SP",
    "cep": "01001000",
    "ddd_telefone_1": "1133334444",
    "email": None,
    "descricao_situacao_cadastral": "ATIVA",
    "qsa": [{"nome_socio": "Dado que não deve ser devolvido"}],
}


class CompanyLookup(unittest.TestCase):
    def test_formatted_and_alphanumeric_documents(self):
        self.assertEqual(cnpj.normalize("19.131.243/0001-97"), DOCUMENT)
        self.assertEqual(cnpj.normalize("12.abc.345/01de-35"), "12ABC34501DE35")

    def test_invalid_input_never_reaches_provider(self):
        with patch.object(cnpj, "urlopen") as request:
            for value in [
                None,
                123,
                "12345678901",
                "00000000000000",
                "https://example.com",
                "A" * 31,
            ]:
                with self.assertRaises(ValueError):
                    cnpj.lookup(value)
            request.assert_not_called()

    def test_mapping_limits_fields_and_formats_contacts(self):
        result = cnpj.company_fields(PUBLIC, DOCUMENT)
        self.assertEqual(result["company"]["document"], "19.131.243/0001-97")
        self.assertEqual(result["company"]["phone"], "(11) 3333-4444")
        self.assertIn("SAO PAULO / SP, CEP 01001-000", result["company"]["address"])
        self.assertEqual(result["company"]["email"], "")
        self.assertNotIn("qsa", result)
        self.assertNotIn("website", result["company"])
        repeated = cnpj.company_fields(dict(PUBLIC, logradouro="DAS FLORES 100"), DOCUMENT)
        self.assertTrue(repeated["company"]["address"].startswith("RUA DAS FLORES 100, CENTRO,"))

    def test_mismatched_or_incomplete_payload_is_refused(self):
        for data in [[], {}, dict(PUBLIC, cnpj="00000000000191"), dict(PUBLIC, razao_social="")]:
            with self.assertRaises(cnpj.LookupError):
                cnpj.company_fields(data, DOCUMENT)

    def test_success_uses_fixed_https_endpoint_and_timeout(self):
        with patch.object(
            cnpj, "urlopen", return_value=io.BytesIO(json.dumps(PUBLIC).encode())
        ) as request:
            self.assertEqual(cnpj.lookup(DOCUMENT)["company"]["name"], PUBLIC["razao_social"])
            self.assertEqual(request.call_args.args[0].full_url, cnpj.API + DOCUMENT)
            self.assertEqual(request.call_args.kwargs["timeout"], 10)

    def test_unavailable_invalid_and_oversized_responses(self):
        for failure in [URLError("offline"), TimeoutError()]:
            with patch.object(cnpj, "urlopen", side_effect=failure):
                with self.assertRaises(cnpj.LookupError) as error:
                    cnpj.lookup(DOCUMENT)
                self.assertEqual(error.exception.status, 503)
        for body in [b"<html>erro</html>", b"x" * (cnpj.MAX_RESPONSE + 1)]:
            with patch.object(cnpj, "urlopen", return_value=io.BytesIO(body)):
                with self.assertRaises(cnpj.LookupError):
                    cnpj.lookup(DOCUMENT)

    def test_not_found_and_bad_request_are_distinct(self):
        for status in [400, 404, 429, 500]:
            with patch.object(
                cnpj, "urlopen", side_effect=HTTPError(cnpj.API, status, "erro", {}, None)
            ):
                with self.assertRaises(cnpj.LookupError) as error:
                    cnpj.lookup(DOCUMENT)
                self.assertEqual(error.exception.status, status if status in (400, 404) else 503)


class CompanyEndpoint(unittest.TestCase):
    def setUp(self):
        self.flow = test_network.NetworkFlow()
        self.flow.setUp()
        self.addCleanup(self.flow.tearDown)
        self.client = self.flow.client

    def test_authenticated_lookup_does_not_save_company_or_revision(self):
        before = self.client.request("/api/state")[1]
        with patch.object(cnpj, "lookup", return_value=cnpj.company_fields(PUBLIC, DOCUMENT)):
            status, body, _ = self.client.request("/api/company/cnpj", {"cnpj": DOCUMENT})
        self.assertEqual(status, 200)
        self.assertEqual(body["company"]["name"], PUBLIC["razao_social"])
        self.assertEqual(self.client.request("/api/state")[1], before)
        self.assertEqual(self.client.request("/company.js")[0], 200)

    def test_login_csrf_origin_and_employee_restrictions(self):
        with patch.object(cnpj, "lookup") as lookup:
            self.assertEqual(
                Client(self.flow.url).request("/api/company/cnpj", {"cnpj": DOCUMENT})[0], 401
            )
            self.assertEqual(
                self.client.request("/api/company/cnpj", {"cnpj": DOCUMENT}, csrf=False)[0], 403
            )
            for _ in range(8):
                self.assertEqual(
                    self.client.request(
                        "/api/company/cnpj", {"cnpj": DOCUMENT}, origin="https://example.com"
                    )[0],
                    403,
                )
            employee = self.flow.employee()
            self.assertEqual(
                employee.request(
                    "/api/password",
                    {
                        "currentPassword": "temporaria-funcionario",
                        "newPassword": "nova-senha-funcionario",
                    },
                )[0],
                200,
            )
            self.assertEqual(employee.login("funcionario", "nova-senha-funcionario")[0], 200)
            self.assertEqual(employee.request("/api/company/cnpj", {"cnpj": DOCUMENT})[0], 403)
            lookup.assert_not_called()

    def test_lookup_errors_have_actionable_statuses(self):
        self.assertEqual(self.client.request("/api/company/cnpj", {"cnpj": "123"})[0], 400)
        with patch.object(cnpj, "lookup", side_effect=cnpj.LookupError("Serviço indisponível")):
            status, body, _ = self.client.request("/api/company/cnpj", {"cnpj": DOCUMENT})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "Serviço indisponível")

    def test_employee_can_consult_clients_without_saving_or_editing_company(self):
        employee = self.flow.employee()
        employee.request(
            "/api/password",
            {"currentPassword": "temporaria-funcionario", "newPassword": "nova-senha-funcionario"},
        )
        self.assertEqual(employee.login("funcionario", "nova-senha-funcionario")[0], 200)
        before = employee.request("/api/state")[1]
        with patch.object(
            cnpj, "lookup", return_value=cnpj.company_fields(PUBLIC, DOCUMENT)
        ) as lookup:
            status, body, _ = employee.request("/api/clients/cnpj", {"cnpj": DOCUMENT})
            self.assertEqual(status, 200)
            self.assertEqual(body["company"]["tradeName"], PUBLIC["nome_fantasia"])
            self.assertEqual(employee.request("/api/company/cnpj", {"cnpj": DOCUMENT})[0], 403)
            self.assertEqual(lookup.call_count, 1)
        self.assertEqual(employee.request("/api/state")[1], before)

    def test_client_lookup_requires_session_csrf_origin_and_current_password(self):
        with patch.object(cnpj, "lookup") as lookup:
            self.assertEqual(
                Client(self.flow.url).request("/api/clients/cnpj", {"cnpj": DOCUMENT})[0], 401
            )
            self.assertEqual(
                self.client.request("/api/clients/cnpj", {"cnpj": DOCUMENT}, csrf=False)[0], 403
            )
            for _ in range(8):
                self.assertEqual(
                    self.client.request(
                        "/api/clients/cnpj", {"cnpj": DOCUMENT}, origin="https://example.com"
                    )[0],
                    403,
                )
            employee = self.flow.employee()
            self.assertEqual(employee.request("/api/clients/cnpj", {"cnpj": DOCUMENT})[0], 403)
            lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
