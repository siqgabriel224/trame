# Clientes, Bordado e DTF

## Cliente e vendedora

Em **Clientes**, pesquise pelo nome, nome fantasia ou CPF/CNPJ. A busca aceita CNPJ com ou sem pontuação e nomes sem acentos. O resultado mostra o documento e a **vendedora responsável**, separada do contato responsável pelo cliente.

Use **Editar cadastro** para informar a vendedora. Esse nome preenche novos pedidos quando o cliente é selecionado e também os novos serviços avulsos. Os pedidos antigos mantêm os responsáveis já registrados; clientes anteriores sem vendedora aparecem como Não informada.

## Quem acessa as novas abas

As abas **Bordado** e **DTF** ficam disponíveis aos perfis **Administrador** e **Bordador(a) — Bordado e DTF**. O funcionário comum não consegue consultar, alterar ou imprimir esses serviços, inclusive tentando as rotas diretamente.

Para liberar um acesso existente, o administrador usa **Minha conta → Acessos dos funcionários → Gerenciar acesso → Perfil**. Alterar o perfil encerra as sessões daquela conta, que precisa entrar novamente. O novo perfil também está disponível ao criar um acesso. As contas existentes não são promovidas automaticamente.

## Registrar serviços em peças do cliente

1. Abra Bordado ou DTF e clique em **Novo serviço**.
2. Selecione o cliente e confira a vendedora.
3. Informe descrição, responsável pela execução, entrada e situação.
4. Informe quantidade, unidade, valor por unidade e preparação/matriz, quando houver.
5. Registre referência do arquivo, matriz e instruções necessárias e salve.

As unidades são peça, metro, aplicação e lote. Quantidades aceitam até três casas decimais: use `1,5` para uma unidade e meia e `1000` para mil, sem separador de milhares. O preço tem duas casas decimais; o total é arredondado para centavos. Por exemplo, 2,5 metros a R$ 45,00 totalizam R$ 112,50.

Os códigos são próprios de cada técnica: **BORD-0001**, **DTF-0001**, e assim por diante. Registrar o serviço não cria OS de confecção, modelos, etapas ou reservas de tecido. O valor da peça trazida pelo cliente não é acrescentado ao serviço. Os pedidos de confecção com bordado ou DTF continuam seguindo seu fluxo normal.

É possível cadastrar um trabalho já realizado selecionando Concluído ou Entregue. A conclusão exige data entre a entrada e hoje, responsável ativo e valor maior que zero. Um cancelamento exige motivo; recebimentos existentes precisam ser anulados com motivo antes de cancelar o serviço.

## Fechamento mensal

Escolha o mês e abra **Fechamento mensal**. Entram os serviços Concluído ou Entregue pela **data de conclusão**, agrupados por cliente. Trabalhos recebidos ou em execução ficam fora, com aviso na tela.

Confira os valores e use **Conferir e fechar mês**. A confirmação informa quantidade de serviços e total. O fechamento preserva os itens, preços, clientes, empresa, pessoa que fechou e horário do registro. Um novo serviço concluído naquele mês também exige reabrir o período, evitando alterações silenciosas no total fechado.

Somente o administrador pode usar **Reabrir com motivo**. Ao fechar novamente, a versão anterior e a justificativa ficam no histórico. Bordado e DTF têm fechamentos independentes.

Use **Imprimir demonstrativo** para o mês inteiro ou **Demonstrativo deste cliente** para uma cobrança individual. O relatório reúne números, datas, descrições, vendedoras, quantidades, valores e saldo.

## Recebimentos depois do fechamento

Os recebimentos continuam disponíveis nos serviços já fechados. Abra **Serviços**, localize o número e use **Registrar recebimento**. O valor deve ser positivo e não pode superar o saldo. Uma anulação mantém o registro original, motivo e identificação da conta que anulou.

Os valores do fechamento são preservados, enquanto o saldo da tela e do demonstrativo considera os recebimentos atuais. O relatório identifica essa atualização. Serviços avulsos têm seus recebimentos nas abas Bordado/DTF; a área Cobranças dos pedidos de confecção continua mostrando as parcelas das OS.

## Dados e cópias

Os serviços e fechamentos usam tabelas próprias no mesmo SQLite local. As cópias SQLite incluem essas tabelas, e **Exportar cópia dos dados**, exclusivo do administrador, também inclui serviços e fechamentos no JSON. Esses registros não são enviados no estado comum das OS, preservando a restrição de acesso.

Na demonstração desta validação foram preparados exemplos de serviços recebidos, em execução, concluídos e entregues, com vendedoras e recebimentos fictícios. Setembro/2026 tem fechamentos das duas técnicas; outubro inclui o fechamento de Bordado feito pela interface. As [capturas de clientes](imagens/clientes-pesquisa-vendedora.png), [Bordado](imagens/bordado-fechamento.png), [DTF](imagens/dtf-servico-avulso.png) e [demonstrativo](imagens/servicos-demonstrativo.png) usam somente dados fictícios.
