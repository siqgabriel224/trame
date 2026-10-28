# Instalação e operação

## Primeira execução

1. Instale Python 3.12 ou superior e extraia o projeto numa pasta com permissão de gravação.
2. Configure a conta remetente conforme [cadastro por e-mail](RECUPERACAO-EMAIL.md).
3. Verifique a conexão com `python iniciar.py --verificar-email`, no mesmo ambiente que iniciará o Tramê.
4. Abra `Abrir Trame.cmd` ou execute `python iniciar.py`.
5. Abra o arquivo `dados/chave-primeiro-acesso.txt` e use a chave na tela inicial.
6. Crie o administrador com senha de pelo menos 12 caracteres e confirme seu e-mail.
7. Cadastre os demais acessos em **Minha conta → Acessos dos funcionários**.

Não compartilhe a chave, o banco ou capturas que mostrem credenciais. A aplicação começa sem clientes e pedidos.

## Banco e backups

O banco padrão fica em `dados/radar.sqlite3`. Ao iniciar, o servidor cria uma cópia diária e um snapshot em `dados/backups-rede/`. Novos snapshots são gerados a cada 15 minutos, durante o uso e também pelo verificador periódico do servidor. Cada cópia passa por `PRAGMA quick_check` antes de substituir o arquivo temporário. São mantidas as 96 versões mais recentes dos snapshots e as 30 cópias diárias mais recentes. Arquivos com outros nomes não entram na limpeza. A retenção só é aplicada depois de uma nova cópia verificada.

O administrador pode consultar o último sucesso e eventuais falhas em **Minha conta**. Uma falha de backup não desfaz um salvamento já confirmado.

O destino pode ser alterado pela variável `TRAME_BACKUP_DIR`, por exemplo para uma pasta protegida em outra unidade. Use um destino exclusivo por instalação e banco; reinicie o Tramê após mudar o ambiente. Uma pasta de sincronização não substitui a verificação das cópias.

Um backup no mesmo disco ajuda contra erros de edição, mas não protege contra perda do computador. Mantenha cópias periódicas em outro local protegido.

Para copiar manualmente, encerre o Tramê com Ctrl+C e copie a pasta `dados` inteira. Para restaurar, mantenha o programa fechado, preserve a pasta atual com outro nome e coloque a cópia em `dados`. Reabra e confira clientes, últimos pedidos e acessos. Não misture arquivos SQLite de cópias diferentes.

## Atualização

Encerre o servidor, preserve uma cópia completa da instalação e substitua somente o código. Não substitua `dados` por uma pasta de demonstração. Confira os pedidos antes de voltar a operar. As migrações existentes adicionam campos sem apagar os registros anteriores; mudanças futuras ainda precisam ser verificadas em cópia do banco.

## Porta ocupada

Feche a outra instância ou execute `python iniciar.py --porta 18744`. O banco continua no mesmo lugar. Não execute duas instâncias sobre o mesmo banco durante atualizações ou restaurações.

## Compatibilidade

Este repositório documenta Python 3.12+ e navegadores atuais. Os pacotes históricos para Windows 7–11 pertencem à instalação anterior e não estão incluídos aqui. A presença de arquivos de compatibilidade não significa que esta entrega foi testada fisicamente em versões antigas do Windows.

## Publicar o código

Execute `python scripts/verificar.py` e revise `git status --short` antes de enviar. A lista de arquivos não deve incluir `dados`, certificados, backups, bancos ou executáveis. Compartilhe somente capturas de uma base fictícia. A pasta original de trabalho não deve ser enviada inteira ao GitHub.

## Restaurar um snapshot

Com o Tramê fechado, preserve a pasta `dados` atual. Crie outra pasta `dados` e copie o snapshot escolhido para ela com o nome `radar.sqlite3`. Não traga arquivos `-wal` ou `-shm` do banco anterior para a nova pasta. Abra o Tramê e confira últimos pedidos, recebimentos, serviços, fechamentos e acessos. Os snapshots incluem todo o banco, inclusive contas e auditoria; proteja o destino como protege os dados originais.
