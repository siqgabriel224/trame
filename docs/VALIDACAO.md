# Validação local — 26/10/2026

Ambiente desta conferência: Windows, Python 3.12.14, SQLite 3.53.1 e cryptography 50.0.2. As bases dos testes foram isoladas da instalação em uso.

## Resultado

- 72 testes Python aprovados: regras comerciais, estoque, produção, entregas, autenticação, autorização, TLS, concorrência, inicialização e consulta CNPJ na empresa e nos clientes.
- Cinco suítes JavaScript aprovadas: cálculos comerciais, operação, alterações por entidade, retorno do login e preenchimento da empresa.
- Sintaxe dos arquivos JavaScript verificada pelo Node.js.
- Análise Ruff sem ocorrências e formatação Python conferida.
- Formatação Prettier conferida em HTML, CSS e JavaScript.
- Lista de arquivos do Git conferida sem banco, chaves, ambientes virtuais ou dependências instaladas.

## Fluxo no navegador

Na base de demonstração, foi criado o pedido fictício **Oficina Semente**, com um modelo de camiseta, 12 peças M e 8 peças G. A R$ 35,90 por unidade, a interface e a persistência apresentaram **R$ 718,00**. O modelo começou aguardando aprovação, com as opções de produção bloqueadas.

O pedido permaneceu depois de recarregar a página. A instância temporária foi encerrada e reaberta pelo `Abrir Trame.cmd`, com o banco fictício e uma porta própria. O navegador voltou a exibir os quatro pedidos, incluindo o criado manualmente. O iniciador foi executado por comando; o duplo clique no Explorer e a abertura automática do navegador não foram validados nesta etapa.

As [capturas](imagens/pedido.png) mostram somente dados fictícios.

## Ainda não validado

O workflow remoto do GitHub, outras versões de Python, Linux, versões antigas do Windows, impressora física e uso diário na empresa não foram verificados nesta preparação. A edição limpa não inclui os executáveis históricos nem promete compatibilidade física com Windows 7.

O banco original e os atalhos da instalação anterior não foram alterados.

## Consulta de CNPJ

A consulta real do CNPJ público usado na documentação da BrasilAPI preencheu razão social, nome fantasia, telefone e endereço no formulário de demonstração. A ausência de e-mail foi informada na tela, sem salvar a empresa automaticamente. O nome fantasia também foi incluído no cabeçalho dos documentos impressos.

Os testes simulam falta de internet, CNPJ não encontrado, resposta inválida e tentativa de consulta sem permissão. Também conferem que trocar o CNPJ, editar campos ou fechar o formulário durante a consulta impede sobrescritas incorretas.

A atualização foi aplicada à instalação da área de trabalho com backup prévio de código e banco. O conteúdo de pedidos e empresa permaneceu idêntico ao backup após o reinício. Durante a atualização foram encontradas duas instâncias do servidor na mesma porta; o servidor agora usa porta exclusiva no Windows, com teste de regressão para impedir a repetição.

Uma execução intermediária apresentou um erro e o resumo não permitiu recuperar o diagnóstico. A execução completa seguinte, com log integral, aprovou os 70 testes. Não foi atribuída uma causa à falha intermediária; acompanhar caso volte a ocorrer.

## Consulta no cadastro de clientes

Na base de demonstração, foi consultado o CNPJ público da documentação, preservado um responsável digitado manualmente, salvo o cliente e reaberto o cadastro para edição. Nome, nome fantasia, documento, telefone, endereço, responsável e observações permaneceram gravados. A consulta não preenche WhatsApp a partir do telefone.

Os testes verificam acesso de funcionários à consulta de clientes, manutenção da restrição de administrador na empresa, sessão, CSRF e troca de senha pendente. O componente compartilhado também invalida respostas ao substituir o formulário de operações.

Uma rodada apresentou WinError 10053 ao testar uma origem recusada. O servidor foi ajustado para consumir corpos pequenos antes de encerrar essa resposta no Windows. As recusas de origem passaram a ser repetidas nos testes. A rodada final aprovou os 72 testes Python, as cinco suítes JavaScript e as verificações estáticas.

A instalação real recebeu a atualização com backup de código e snapshot do banco. Cadastros, pedidos e dados da empresa permaneceram idênticos ao snapshot após o reinício.
