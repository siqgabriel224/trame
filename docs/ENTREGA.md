# Preparação para o GitHub — 26/10/2026

Esta pasta é uma edição limpa do código. A instalação anterior e seus dados foram preservados na pasta `Radar de Pedidos e Prazos`.

Foram selecionados o servidor, a interface, as regras de negócio, o gerador de QR Code e os testes. Scripts pontuais de reescrita do código, ferramentas de build específicas do computador, imagens antigas, runtimes e bancos não fazem parte desta entrega.

O iniciador `iniciar.py` oferece uma entrada local independente de caminhos pessoais. A documentação descreve o fluxo atual e separa recursos existentes de validações ainda pendentes. O workflow do GitHub verifica Windows/Linux e Python 3.12/3.13; sua execução remota só poderá ser confirmada depois da publicação.

O utilitário `remove_examples.py` foi mantido porque os testes históricos verificam a preservação de registros na limpeza de exemplos. Ele não é executado na inicialização. `configure_network.py` permanece para os testes de certificado e uso técnico opcional; a edição padrão continua local.

A licença geral ainda não foi escolhida. Os avisos e a licença do QR Code foram preservados.

## Alterações no código

- Python formatado com Ruff; HTML, CSS e JavaScript com Prettier.
- Removidos imports e variáveis sem uso identificados pela análise estática.
- Retorno após login restrito à mesma origem, incluindo rejeição de barras invertidas e caracteres de controle.
- Testes de regressão para o retorno do login e para impedir criação de dados quando a porta de inicialização está ocupada.
- Mensagens de conexão e salvamento ajustadas ao uso em um único computador.
- Montagem das linhas de pedidos separada da filtragem da lista, calculando valores e pendências uma vez por registro.

Os formatadores são dependências de desenvolvimento. O aplicativo local continua sem dependências Python externas e sem necessidade de pacotes npm.
