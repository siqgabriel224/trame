# Cadastro e recuperação por e-mail

## Confirmação de novas contas

Ao cadastrar uma conta, o Tramê envia um código ao endereço informado e mantém o acesso pendente. Na tela de entrada, a pessoa deve clicar em **Confirmar meu e-mail**, informar o e-mail e o código, e clicar em **Confirmar e ativar minha conta**. Depois entra com a senha temporária e define sua senha pessoal. Isso também se aplica ao primeiro administrador.

O código expira em 15 minutos, só pode ser usado uma vez e é armazenado como resumo criptográfico. O reenvio invalida o código anterior, exige um intervalo de um minuto e tem limite de tentativas. A recuperação de senha não ativa contas pendentes. Gmail, Outlook e outros domínios são aceitos. Configuração ausente ou inválida impede o cadastro antes de gravar a conta. Se o provedor falhar na entrega depois da gravação, a conta permanece pendente, sem acesso; corrija o envio e use **Confirmar meu e-mail → Reenviar código**. O intervalo de um minuto entre códigos continua valendo.

Contas anteriores à implantação continuam com seus acessos. Alterar o endereço exige nova confirmação e encerra as sessões; o único administrador confirmado deve primeiro cadastrar e confirmar outro administrador para poder trocar seu endereço. Uma conta de administrador ainda pendente não substitui o último administrador ativo confirmado.

Novas contas usam e-mail. Gmail, Outlook e outros endereços são aceitos. Contas antigas continuam entrando pelo login anterior; o administrador pode incluir o e-mail em Minha conta → Acessos dos funcionários → Gerenciar acesso.

Na tela de entrada, clique em **Esqueci minha senha**, informe o e-mail cadastrado e use o código recebido para definir outra senha. O código vale por 15 minutos, só funciona uma vez e a recuperação encerra as sessões anteriores. Há limite de tentativas. O banco guarda somente o resumo criptográfico do código.

## Conta remetente

O servidor precisa de internet e de uma conta SMTP. A conta que envia pode ser Gmail e os destinatários podem ser Gmail, Outlook ou outros provedores.

Configure as variáveis de ambiente do processo que inicia o Tramê:

| Variável | Valor |
| --- | --- |
| TRAME_SMTP_HOST | Servidor SMTP do remetente |
| TRAME_SMTP_PORT | 587 para STARTTLS ou 465 para SSL |
| TRAME_SMTP_SECURITY | starttls ou ssl |
| TRAME_SMTP_FROM | E-mail remetente |
| TRAME_SMTP_USER | Usuário SMTP |
| TRAME_SMTP_PASSWORD | Credencial SMTP específica do aplicativo |

O transporte exige criptografia TLS. Nunca coloque credenciais no código, em commits ou em mensagens do chat. Reinicie o servidor depois de configurar o ambiente. Se não houver configuração, o Tramê informa que o envio ainda não está disponível. O envio real precisa ser validado com uma conta configurada.

## Conferir a instalação antes do primeiro acesso

A tela de primeiro acesso avisa quando a conta remetente não está configurada e impede o envio do formulário. Configure o ambiente do processo que inicia o Tramê e execute:

```sh
python iniciar.py --verificar-email
```

A verificação abre uma conexão TLS, autentica e consulta o servidor, sem enviar mensagens e sem abrir o banco. Ela não garante a entrega na caixa de entrada: a primeira confirmação real ainda deve ser conferida, inclusive na pasta de spam. Depois, inicie o Tramê normalmente.

Os envios HTTP ocorrem depois da confirmação da transação e da liberação do bloqueio de gravação. Assim, um SMTP lento não impede outra pessoa de salvar pedidos. Os códigos ficam apenas em memória durante o envio; o banco mantém seus resumos criptográficos. Se o processo for encerrado entre salvar e entregar, solicite o reenvio.
