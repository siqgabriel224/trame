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
| `cnpj.py` | Consulta opcional à BrasilAPI, com tempo e tamanho de resposta limitados |
| `web/company.js` | Preenchimento dos dados públicos sem salvamento automático |
| `network.py` | HTTP autenticado, proteção de origem, conflitos e backup |
| `web/domain.js` | Cálculos compartilhados entre telas e impressão |
| `web/commerce.js` | Formulários e apresentação de valores |
| `web/operations.js` | Operação de produção, materiais e entregas |
| `web/access.js` | Sessão e envio de alterações por entidade |
| `services.py` | Serviços avulsos, recebimentos e versões do fechamento mensal em tabelas próprias |
| `web/services.js` | Lançamentos e fechamento de Bordado/DTF, separados das OS |
| `web/theme.css` | Cores, tipografia, foco e fundamentos compartilhados entre aplicação, login e impressão |
| `demonstracao.py` | Inicialização local com banco e acesso de demonstração separados |
| `demo_data.py` | Histórico fictício construído pelas validações comerciais da aplicação |
| `vendor/qrencoder.py` | QR Code, com licença e autoria próprias |

## Decisões de domínio

**Aprovação por modelo.** Uma OS pode conter peças diferentes. A aprovação de um modelo não libera os outros. A mudança de layout invalida a aprovação anterior e mantém o histórico.

**Dinheiro em centavos.** Valores são inteiros. O total reúne quantidade × preço unitário, adicionais por peça, preparações únicas, frete e desconto. Recebimentos anulados permanecem registrados e deixam de compor o saldo.

**Quantidades de material em milésimos.** Reserva e consumo são movimentos distintos. O sistema confere disponibilidade e impede estoque negativo nas operações cobertas pelas regras.

**Concorrência por registro.** Alterações em registros diferentes podem ser combinadas. Edições incompatíveis do mesmo registro retornam conflito, evitando substituir silenciosamente o trabalho anterior.

**Histórico preservado.** Arquivamento, anulação e desativação preservam referências. O banco mantém o estado de negócio como JSON revisionado, além das tabelas de acesso. Isso simplifica a aplicação local; consultas analíticas grandes e múltiplas unidades exigiriam rever o modelo.

## Execução e medidas

As assinaturas de execução são registradas nas etapas, com executor, data, conta autenticada que confirmou, origem do registro e horário do servidor. As rotas de alteração exigem assinatura na nova conclusão, conferem o vínculo do funcionário conectado e preservam etapas assinadas. Administradores podem transcrever a execução conforme a OS em papel, com essa origem identificada. Conclusões antigas não recebem assinaturas presumidas. Esse registro operacional não usa certificado digital.

As grades continuam armazenadas como quantidades por chave: Feminino PP–GG, Masculino PP–GG e Sob medida. O texto `measurements` acompanha as peças sob medida, com validação de quantidade e conteúdo. Chaves antigas são mantidas, evitando atribuição presumida de gênero ou alteração de entregas anteriores.

## Serviços avulsos

Serviços avulsos usam `service_jobs` e `service_closings` no SQLite existente. Cada alteração compara a revisão do registro; a numeração é independente por técnica. As rotas `/api/services` e `/api/services/*` exigem administrador ou perfil `embroiderer`, sessão atualizada e, nas alterações, origem e CSRF. O estado compartilhado das OS não inclui essas tabelas. A exportação completa é exclusiva de administrador e reúne os dois conjuntos.

O fechamento usa a data de conclusão dos serviços e guarda uma cópia dos itens e valores. Alterações em serviços concluídos no período fechado são recusadas; recebimentos posteriores preservam o total e atualizam o saldo. A reabertura exige administrador e justificativa, e o próximo fechamento preserva a versão anterior.

## Limites

Não há emissão fiscal, transação bancária, assinatura digital com certificado ou sincronização entre computadores. O iniciador público força uso local. O suporte de rede existente no código requer configuração de certificado e administração própria; não faz parte do fluxo padrão.

O servidor usa a biblioteca padrão do Python e não foi dimensionado para hospedagem pública. Testes automatizados não substituem avaliação com usuários, impressora e dados de uma operação real.

## Consulta de CNPJ

O botão em Dados da empresa envia apenas o CNPJ para a rota autenticada `POST /api/company/cnpj`. O servidor consulta um endereço HTTPS fixo da BrasilAPI, sem enviar contas, pedidos ou dados do banco. A consulta fica restrita a administradores com senha atualizada, valida origem e CSRF e não mantém o bloqueio de escrita dos pedidos enquanto aguarda a fonte externa.

São aceitos CNPJs numéricos e alfanuméricos no formato documentado pela fonte. A validação cadastral é feita pelo provedor. O retorno é reduzido a razão social, nome fantasia, CNPJ, endereço, telefone, e-mail e situação cadastral; quadro societário e outros dados não são repassados para o navegador.

Consultar não grava empresa nem revisão. Campos não informados pela fonte e edições feitas enquanto a resposta chega são preservados. Trocar o CNPJ ou fechar o formulário invalida uma resposta pendente. O usuário revisa o resultado e escolhe Salvar empresa.

O cadastro e a edição de clientes usam o mesmo componente de preenchimento pela rota `POST /api/clients/cnpj`. Essa rota permite administradores e funcionários autenticados com senha atualizada, acompanhando as permissões de cadastro de clientes. A consulta da própria empresa permanece exclusiva de administradores. O resultado preenche nome, nome fantasia, documento, telefone, e-mail e endereço; não presume WhatsApp nem responsável pelo cliente. Trocar o formulário compartilhado de operações também invalida consultas pendentes.
