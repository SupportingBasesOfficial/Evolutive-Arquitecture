# Motor de conformidade

## Estágios

O motor é dividido em estágios para impedir que descoberta, confiança, inspeção e decisão se misturem:

1. **Validar configuração** — lê a configuração explícita do consumidor.
2. **Verificar fonte** — confere SHA-256, versão e manifesto do bundle constitucional.
3. **Planejar** — seleciona perfis, regras e raízes autorizadas sem ler o conteúdo dessas raízes.
4. **Inspecionar** — o broker enumera e abre somente arquivos autorizados, monta uma requisição fechada e a entrega a verificadores internos registrados.
5. **Relatar** — valida e emite evidências de conformidade sem modificar o projeto consumidor.

A implementação atual possui os cinco estágios, mas mantém cada autoridade separada. Planejamento continua sendo não-inspecionante; inspeção só ocorre quando o comando integrado entra explicitamente no estágio seguinte.

## Limite do planejamento

`scripts/plan_compliance.py` não enumera nem lê arquivos das raízes do consumidor. O plano declara que nenhuma inspeção foi executada nessa etapa, e os testes mantêm um arquivo sentinela para garantir que conteúdo do consumidor não vaze para o plano.

Essa propriedade continua válida mesmo com a existência posterior do estágio de inspeção: planejar não concede implicitamente autoridade para ler conteúdo.

## Inspeção controlada

A inspeção é mediada por componentes com responsabilidades distintas:

- o broker de escopo enumera somente metadados autorizados;
- o broker de conteúdo aplica extensão, tamanho, UTF-8 e hash antes de materializar conteúdo;
- o checker recebe uma requisição fechada com caminhos relativos e conteúdo já autorizado;
- o checker não recebe a raiz livre do consumidor;
- manifestos de checker pertencem ao produtor e suas capacidades são validadas antes da execução.

O comando integrado também recusa autovalidação e sobreposição entre a árvore do produtor e a árvore do consumidor.

## Relatório e cadeia de evidências

O relatório final é validado por schema. Antes de emiti-lo, o orquestrador compara contagens e bytes observados entre broker, requisição e resultado do checker, além de registrar hashes da requisição canônica e do manifesto utilizado.

Uma divergência na cadeia de evidências invalida a execução; ela não é convertida em sucesso parcial.

## Estados das regras

Regras `proposed` permanecem inelegíveis para enforcement. Mudanças para `experimental`, `active`, `deprecated` ou `revoked` são governadas pelo contrato descrito em `docs/RULE_LIFECYCLE.md`.

Somente regras `active` podem produzir obrigação bloqueante. A promoção para `active` exige uma decisão aprovada com mecanismo de enforcement declarado como pronto para o nível definido pela própria regra.

## Próxima fronteira

A próxima evolução do motor não é conceder mais autoridade aos checkers. É ampliar cobertura sem romper o boundary atual: novos verificadores por linguagem ou plataforma devem continuar registrados pelo produtor, receber somente a requisição já resolvida pelos brokers e operar sob capacidades explícitas.

Qualquer futura abertura para plugins externos, subprocessos, rede ou ambiente deve ser tratada como nova fronteira de confiança e exige contrato próprio antes de implementação.
