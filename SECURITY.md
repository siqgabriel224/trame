# Dados e segurança

A edição padrão atende somente em `127.0.0.1`. Não exponha o servidor diretamente à internet. A configuração opcional de rede exige TLS e revisão de quem administra os computadores.

As contas são armazenadas no banco local, com hash de senha e sessões controladas pelo servidor. As rotas autenticadas verificam origem e token CSRF. Os testes exercitam autorização, revogação de sessão, conflitos e bloqueio do último administrador.

Senhas, chaves de primeiro acesso, certificados e banco de dados não devem aparecer em issues, capturas ou commits. Para relatar um problema, descreva o comportamento sem incluir dados de clientes. Se houver uma credencial exposta, revogue-a antes de compartilhar qualquer reprodução.

O projeto está em desenvolvimento e não passou por auditoria independente. Backups precisam da mesma proteção do banco principal.
