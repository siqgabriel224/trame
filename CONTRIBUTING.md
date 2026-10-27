# Como contribuir

Use Python 3.12+ e Node.js 22+. As dependências de teste estão em `requirements-dev.txt`.

Antes de propor uma mudança, descreva qual operação está incorreta e um exemplo reproduzível com dados fictícios. Mudanças em aprovação, recebimentos, estoque ou entregas devem incluir um teste da regra e preservar os registros anteriores.

Execute `python scripts/verificar.py`. Não versione bancos, credenciais, certificados, ambientes virtuais ou cópias de clientes. Evite novas dependências para funções que a biblioteca padrão já resolve.

Mantenha mensagens da interface em português. Prefira nomes que descrevam a operação e comentários que expliquem uma decisão; evite comentários que apenas repitam o código. O backend deve validar toda alteração recebida do navegador.

O código de terceiros em `vendor` deve conservar os avisos de licença. A licença geral do projeto ainda não foi definida.
