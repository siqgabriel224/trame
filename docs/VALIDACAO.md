# Validação local — 26/10/2026

Ambiente desta conferência: Windows, Python 3.12.14, SQLite 3.53.1 e cryptography 50.0.2. As bases dos testes foram isoladas da instalação em uso.

## Resultado

- 59 testes Python aprovados: regras comerciais, estoque, produção, entregas, autenticação, autorização, TLS, concorrência e inicialização.
- Quatro suítes JavaScript aprovadas: cálculos comerciais, operação, alterações por entidade e retorno do login.
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
