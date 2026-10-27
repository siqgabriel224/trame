# Arquitetura

O navegador acessa um servidor HTTP local. O servidor valida cada alteração e grava o estado operacional no SQLite. A interface não decide sozinha se uma operação é permitida.

```text
Interface (web/)
       │ HTTP + sessão + CSRF
       ▼
server.py ── network.py ── access.py
       │
       ├── operations.py: regras de produção, estoque e entregas
       └── dados/radar.sqlite3: estado, contas e auditoria
```

## Responsabilidades

| Arquivo | Responsabilidade |
| --- | --- |
| `iniciar.py` | Entrada local, seleção de porta e abertura do navegador |
| `server.py` | Rotas, validação comercial, revisão dos registros e persistência |
| `operations.py` | Cadastros, etapas, materiais, parcelas e entregas |
| `access.py` | Senhas, sessões, perfis e auditoria |
| `network.py` | HTTP autenticado, proteção de origem, conflitos e backup |
| `web/domain.js` | Cálculos compartilhados entre telas e impressão |
| `web/commerce.js` | Formulários e apresentação de valores |
| `web/operations.js` | Operação de produção, materiais e entregas |
| `web/access.js` | Sessão e envio de alterações por entidade |
| `vendor/qrencoder.py` | QR Code, com licença e autoria próprias |

## Decisões de domínio

**Aprovação por modelo.** Uma OS pode conter peças diferentes. A aprovação de um modelo não libera os outros. A mudança de layout invalida a aprovação anterior e mantém o histórico.

**Dinheiro em centavos.** Valores são inteiros. O total reúne quantidade × preço unitário, adicionais por peça, preparações únicas, frete e desconto. Recebimentos anulados permanecem registrados e deixam de compor o saldo.

**Quantidades de material em milésimos.** Reserva e consumo são movimentos distintos. O sistema confere disponibilidade e impede estoque negativo nas operações cobertas pelas regras.

**Concorrência por registro.** Alterações em registros diferentes podem ser combinadas. Edições incompatíveis do mesmo registro retornam conflito, evitando substituir silenciosamente o trabalho anterior.

**Histórico preservado.** Arquivamento, anulação e desativação preservam referências. O banco mantém o estado de negócio como JSON revisionado, além das tabelas de acesso. Isso simplifica a aplicação local; consultas analíticas grandes e múltiplas unidades exigiriam rever o modelo.

## Limites

Não há emissão fiscal, transação bancária, assinatura digital ou sincronização entre computadores. O iniciador público força uso local. O suporte de rede existente no código requer configuração de certificado e administração própria; não faz parte do fluxo padrão.

O servidor usa a biblioteca padrão do Python e não foi dimensionado para hospedagem pública. Testes automatizados não substituem avaliação com usuários, impressora e dados de uma operação real.
