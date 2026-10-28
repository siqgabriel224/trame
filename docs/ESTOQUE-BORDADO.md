# Estoque do bordado: cores e códigos

O cadastro contém tipo, código, grupo para filtro, unidade, saldo inicial e estoque mínimo. A marca padrão de novas linhas é Zenith e o nome interno é gerado automaticamente. Nome, marca, fornecedor, situação e observações ficam fora do formulário; metadados antigos e movimentações são preservados.

A amostra é consultada exclusivamente pelo código Zenith, por exemplo 2228. Alterar o grupo para filtro não altera o tom. Códigos conhecidos preenchem inicialmente o grupo; o usuário pode ajustá-lo para organizar sua busca. Códigos ausentes são indicados como não localizados, sem inventar uma cor pelo nome do grupo.

A tabela local web/zenith-colors.json contém 286 códigos lisos da cartela digital Zenith 25 (colunas 1 a 13). Tons são aproximações extraídas das fotografias da cartela, não valores RGB oficiais nem garantia de correspondência física. Metálicas e multicores não estão incluídas. Códigos e zeros iniciais são preservados, com alias explícito 853 para 0853. Consulta e filtros funcionam sem internet.

Fonte: https://cdn.sistemawbuy.com.br/arquivos/add7561ecda3ba37f1a384cd925d3d94/catalogos/cartela-de-cores-zenith-linhanyl-68f108049b039.pdf

O JSON registra SHA256, origem, posição de cada amostra e método; scripts/extrair_cartela_zenith.py documenta a extração. O PDF e as imagens não são distribuídos no repositório. Para refazer a extração, instale Pillow separadamente, renderize as páginas 2 a 4 a 140 dpi como `pagina-2.png` a `pagina-4.png` e execute `python scripts/extrair_cartela_zenith.py CAMINHO_DA_PASTA`, com `cartela.pdf` nessa mesma pasta.

Verificação: consulta por código independente do grupo, códigos desconhecidos, alias, preservação dos dados antigos, permissões HTTP e demonstração isolada.
