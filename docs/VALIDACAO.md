# Validação local — 26 e 27/10/2026

Ambiente desta conferência: Windows, Python 3.12.14, SQLite 3.53.1 e cryptography 50.0.2. As bases dos testes foram isoladas da instalação em uso.

## Resultado

- 85 testes Python aprovados: regras comerciais, estoque, produção, entregas, autenticação, autorização, TLS, concorrência, inicialização, consulta CNPJ, demonstração, medidas, assinaturas e serviços avulsos.
- Seis suítes JavaScript aprovadas: cálculos comerciais, operação, alterações por entidade, retorno do login, preenchimento CNPJ, confirmação da empresa e pesquisa/cálculo de serviços.
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

As verificações no navegador usam bases separadas. O conteúdo do banco original foi preservado nas atualizações descritas abaixo.

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

## Interface e demonstração com histórico

Foram revisados o tema compartilhado, a aplicação, o acesso e a impressão. A conferência visual cobriu pedidos, orçamentos, clientes, produção, estoque, cobranças, funcionários, detalhes da OS, formulário de pedido e dados da empresa. As larguras de 390, 900 e 1440 pixels foram exercitadas. No celular, a página permaneceu sem transbordamento horizontal; a tabela tem sua própria rolagem. O formulário longo manteve os botões do rodapé acessíveis. A prévia da OS foi conferida no computador e no celular; a impressão física continua pendente.

Os dados da empresa abriram com campos desabilitados e sem o botão Salvar. O lápis abriu a confirmação. Cancelar manteve os campos bloqueados; confirmar liberou a edição; fechar e reabrir bloqueou novamente. Os testes JavaScript também verificam essa sequência.

A nova demonstração contém 32 documentos com conversões de orçamento, 12 clientes, oito funcionários e dez materiais. A construção usa as mesmas validações comerciais do servidor, incluindo aprovações, consumo de estoque, parcelas, anulação e entrega parcial. Os testes conferem a consistência do estado e recusam iniciar a demonstração em um processo já configurado para outra instalação.

O servidor da demonstração foi encerrado e o novo atalho **Tramê — Demonstração** foi acionado. Depois da reabertura, o navegador exibiu novamente os 12 pedidos em aberto, cinco orçamentos em negociação e os mesmos totais. A conferência visual ocorreu no navegador integrado; o duplo clique manual no Explorer não foi testado.

A instalação principal recebeu os arquivos revisados depois de backup do código e do SQLite. Após reiniciar, o estado operacional, a revisão e todos os registros de usuários permaneceram iguais ao snapshot. A nova folha de tema respondeu e a tela de login da instalação principal foi aberta. A demonstração continua com outro banco e outra porta.

As [capturas atuais](imagens/demo-painel.png), a [produção](imagens/demo-producao.png), a [confirmação da empresa](imagens/demo-empresa-confirmacao.png) e a [prévia da OS](imagens/demo-os.png) contêm somente dados fictícios.

## Grades, edição e execução da OS — 27/10/2026

A suíte completa aprovou 79 testes Python, incluindo o fluxo autenticado de um funcionário vinculado ao executor: orçamento, conversão em OS, aprovação, produção, assinatura, recebimentos e entrega. A assinatura usa a conta real da sessão, desconsidera identidade enviada pelo navegador, recusa outros funcionários e preserva registros assinados. Também foram verificadas medidas obrigatórias, quantidades, conclusões antigas sem assinatura e bloqueio de uma nova transição para Pronto sem etapas assinadas.

As cinco suítes JavaScript passaram, incluindo busca por número com zeros e prefixo, distinção entre OS-0021 e OS-0121, preservação da grade anterior, separação Feminino/Masculino e ordenação das etapas sem modificar os registros de origem.

No navegador, a busca OS-0001 encontrou um registro arquivado. A OS-0022 foi editada pela lista e teve sua descrição salva. O modelo foi alterado para 12 peças Feminino PP, 20 Masculino GG e duas sob medida; ao reabrir duas vezes, o total permaneceu em 34 peças, com texto e um único campo de quantidade sob medida. A prévia da OS mostrou as grades, as medidas, o número junto ao modelo e as sete etapas preparadas. Repetir a preparação não duplicou etapas.

Na OS-0016 fictícia, foi registrada a conclusão do bordado por João Alves através da conta de demonstração. A tela e a tabela impressa mostraram nome, data e conta que registrou; a etapa deixou de oferecer edição. As demais etapas mantiveram suas situações e nenhuma assinatura antiga foi presumida. A produção em largura de 390 pixels permaneceu sem transbordamento horizontal da página.

A instalação principal recebeu os arquivos após backup. Estado operacional, revisão e todos os usuários permaneceram idênticos ao snapshot após o reinício. As alterações de exemplo foram feitas exclusivamente na demonstração. Impressão física e uso diário continuam pendentes de avaliação.

## Clientes e serviços avulsos — 27/10/2026

Os novos testes verificam pesquisa por nome sem acento e CNPJ com ou sem máscara, valores por unidade fracionária e manutenção de mil unidades ao reabrir o formulário. No servidor, foram verificados o perfil Bordador(a), bloqueio do funcionário comum e de acessos sem sessão/CSRF/origem válida, separação entre técnicas e OS, numeração, vendedora, valores, revisões, recebimentos, anulação e exportação.

O fechamento foi testado com serviços concluídos e pendentes. Foram recusadas alterações em itens fechados e inclusões tardias no período; recebimentos posteriores mantiveram a cópia do fechamento. A reabertura exigiu administrador e motivo, e o fechamento seguinte preservou a versão anterior.

Na interface, o CNPJ fictício sem máscara encontrou o cliente e exibiu sua vendedora. O cadastro de um bordado avulso de mil peças a R$ 1,50 e R$ 20,00 de preparação resultou em R$ 1.520,00. A reabertura preservou 1000 no campo de quantidade e a vendedora preenchida a partir do cliente. O fechamento de Bordado/10-2026 reuniu três serviços, totalizando R$ 2.635,00, e deixou dois pendentes fora. O fluxo de fechar, reabrir com motivo, fechar novamente e receber R$ 50,00 depois do fechamento foi conferido na base fictícia.

O demonstrativo do cliente apresentou R$ 1.790,00 de serviços, R$ 320,00 recebidos e saldo de R$ 1.470,00. DTF exibiu seus lançamentos e quantidades em metros separadamente. A opção Bordador(a) apareceu no formulário de acessos, sem promover nenhuma conta existente. Os exemplos de serviços foram criados somente na demonstração e não geraram nem alteraram OS ou etapas de confecção. A prévia de impressão foi conferida; impressão física continua pendente.
