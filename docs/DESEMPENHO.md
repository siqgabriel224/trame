# Desempenho e carregamento de layouts

## Alterações

- A interface e os documentos de impressão solicitam `/api/state` com `X-Trame-Layouts: links`. Os layouts atuais e os do orçamento histórico são representados por URLs locais autenticadas, vinculadas ao pedido, modelo e conteúdo. A imagem é transferida quando o navegador precisa exibi-la.
- Clientes sem esse cabeçalho continuam recebendo imagens em base64. A exportação e os backups permanecem completos e independentes desses links. Não há migração destrutiva do banco.
- No salvamento, o servidor resolve os links somente para o mesmo pedido/modelo/conteúdo persistido. Referências alteradas ou antigas geram conflito. Um novo upload continua sujeito às validações e à exigência de nova aprovação. Reanexar exatamente o mesmo arquivo preserva a aprovação.
- Migrações de schema são reaproveitadas entre conexões. A identidade do arquivo e a versão do schema são verificadas para detectar troca do banco ou alterações nas tabelas. O cache é limitado a 16 assinaturas.
- Há um único snapshot de leitura em cache, isolado por banco e revisão. Leituras completas também comparam o conteúdo persistido; resultados editáveis são copiados para não contaminar outros usuários. Imagens reutilizam o snapshot da revisão atual sem reler o JSON inteiro.
- Imagens persistidas que não mudaram deixam de ser decodificadas novamente na validação de cada salvamento. Imagens novas ainda são verificadas.
- Comparações de registros usam índices por identificador no navegador e no servidor, evitando buscas completas repetidas.

## Medição reproduzível

Execute na raiz do projeto:

```sh
python scripts/medir_desempenho.py
```

O script cria e remove um banco temporário. Não usa o banco operacional. O cenário tem 100 pedidos, 200 layouts de 64 KiB e campos fictícios. São médias locais, sem simular uma empresa ou medir o tempo completo de uma ação na interface.

| Medida | Antes | Depois |
| --- | ---: | ---: |
| JSON dos pedidos transmitido à interface | 17.564.287 bytes | 104.647 bytes |
| Validação com layouts inalterados, média de 3 execuções | 251,1 ms | aproximadamente 14–19 ms |
| Abrir/fechar conexão já inicializada, média de 50 execuções | 28,15 ms | aproximadamente 1,9–2,3 ms |

A redução do JSON foi de aproximadamente 99,4%. As imagens ainda precisam ser transferidas quando visualizadas; essa economia é na listagem, nas atualizações e nos salvamentos que antes repetiam os dados de todas elas.

Na versão otimizada, a mesma medição comparou a leitura sem cache com a leitura com cache aquecido: aproximadamente 70 ms e 37 ms, respectivamente. A consulta de imagem usa apenas a revisão para aproveitar o cache já carregado.

## Verificações e limites

`test_performance.py` cobre autenticação das imagens, exportação completa, salvamentos com links, conflitos, rejeição de uploads inválidos, impressão do orçamento histórico após troca de layout, invalidação do cache e troca de arquivo/schema. `test_layouts.cjs` verifica que o mesmo arquivo não perde a aprovação. A suíte de comparação de alterações também verifica que listas grandes não causam varreduras quadráticas na detecção de exclusões.

O banco ainda grava o estado comercial como JSON. Esta etapa reduz transferência, processamento repetido e buscas; não elimina o custo de regravar um histórico muito grande. Separar entidades e anexos no armazenamento e paginar o histórico continuam como evolução de arquitetura, a ser medida em uma base de teste maior. Nunca substitua o SQLite enquanto o Tramê estiver aberto: encerre o aplicativo para manutenção/restauração e reinicie para carregar a nova cópia.
