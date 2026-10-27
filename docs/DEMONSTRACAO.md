# Explorar o Tramê

No Windows, abra **Abrir Demonstracao.cmd**. O navegador abre em `http://127.0.0.1:18750`.

- Usuário: `demo`
- Senha: `Trame-Demo-2026!`

Esse acesso existe somente na demonstração. A instalação de uso normal continua com suas próprias contas e sem senha padrão.

A base fictícia é criada em `.demo/trame-demo.sqlite3`, separada de `dados/radar.sqlite3`. As duas instalações podem funcionar ao mesmo tempo. Uma faixa amarela identifica as telas da demonstração, e suas alterações ficam gravadas para a próxima abertura.

## O que explorar

A primeira abertura prepara aproximadamente três meses de operação: 12 clientes, oito funcionários, dez materiais e 32 documentos, incluindo orçamentos convertidos. As datas se ajustam ao dia da criação.

| Tela | Exemplos disponíveis |
| --- | --- |
| Pedidos | Entregues, arquivados, atrasados, em produção e prontos para expedição |
| Aprovações | Layouts pendentes e um layout substituído que exige nova aprovação |
| Produção | Costura, bordado, silk, DTF e acabamento; filtre por andamento e funcionário |
| Estoque | Reservas, consumo, saldo baixo e material sem estoque |
| Cobranças | Parcelas vencidas e futuras, recebimentos parciais e pedidos pagos |
| Orçamentos | Propostas abertas, vencidas e cópia do orçamento convertido em OS |

O pedido **OS-0021, Padaria do Largo**, tem entrega parcial e saldo a receber. A **OS-0023, Festival Raízes**, tem uma segunda versão do layout aguardando aprovação. A **OS-0014, Café Horizonte**, preserva um recebimento anulado com motivo. Use o filtro Todos para encontrar os pedidos antigos.

Os desenhos das peças também são fictícios. Nenhum dado foi extraído da instalação real. Os CNPJs, contatos e endereços de exemplo não representam cadastros válidos.

## Dados da empresa

O formulário abre somente para leitura. Clique no lápis e confirme **Sim, liberar edição** para alterar os campos. As mudanças só são aplicadas ao clicar em **Salvar empresa**. Fechar ou cancelar volta a bloquear a edição na próxima abertura. A permissão de administrador continua necessária.

## Recomeçar

Encerre o servidor da demonstração com Ctrl+C e execute:

```sh
python demonstracao.py --recriar
```

O banco fictício anterior é guardado em uma subpasta `.demo/arquivo-DATA-HORA`. O comando só recria a demonstração e recusa uma porta ocupada por outra instalação. A opção `--data 2026-10-26` permite fixar uma data para reproduzir as capturas. Sem `--recriar`, a data não altera uma base já criada.

A operação é local. Apenas a consulta opcional de CNPJ requer internet.
