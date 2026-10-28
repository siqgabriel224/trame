# Excluir cadastros e lançamentos

Os botões **Excluir** estão disponíveis em pedidos, orçamentos, modelos, clientes, funcionários, materiais, produtos prontos, serviços de Bordado e DTF, empresas contratantes e insumos do estoque de bordado.

A confirmação mostra o registro selecionado, exige marcar a caixa de ciência. O servidor também exige essa confirmação e verifica sessão, permissões e versão dos dados. Funcionários só podem ser excluídos por administradores. A empresa própria continua sendo gerenciada em Dados da empresa.

A exclusão retira o cadastro das telas, preservando os dados históricos e a auditoria no banco. Pedidos com recebimentos ou reservas pendentes exigem anulação dos recebimentos ou liberação das reservas. Serviços em mês fechado exigem reabertura; serviços com valores recebidos exigem anulação prévia. Modelos com produção ou entregas registradas são preservados dentro do pedido; nesse caso, a exclusão é feita no pedido completo.

Recebimentos, entregas, reservas, assinaturas e movimentações mantêm seus controles de anulação, liberação ou correção, preservando o histórico financeiro e de estoque.
