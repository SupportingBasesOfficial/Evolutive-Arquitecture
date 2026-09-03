# Ciclo de vida das regras

O status de uma regra não é um campo editorial. Ele representa uma decisão normativa e, exceto pelo estado inicial `proposed`, deve ser derivável de uma cadeia de decisões aprovada, versionada e auditável.

## Estados

- `proposed`: proposta sem força de enforcement. É o estado inicial de toda regra.
- `experimental`: regra em adoção controlada para coleta de evidências, falsos positivos, custos e lacunas.
- `active`: regra normativa apta ao enforcement declarado.
- `deprecated`: regra ainda existente, mas destinada à retirada ou substituição.
- `revoked`: regra encerrada. O ID continua reservado e não pode ser reutilizado.

## Transições permitidas

As transições canônicas são:

- `proposed -> experimental`
- `proposed -> active`
- `proposed -> revoked`
- `experimental -> active`
- `experimental -> revoked`
- `active -> deprecated`
- `active -> revoked`
- `deprecated -> active`
- `deprecated -> revoked`

`revoked` é terminal. Uma regra revogada que precise ser retomada deve originar uma nova regra com novo ID e relação explícita de histórico quando aplicável.

## Registro de decisão

Toda transição aprovada deve possuir um documento em:

`decisions/rules/<RULE_ID>/<VERSION>-<TO_STATUS>-approved.yaml`

Decisões rejeitadas podem ser preservadas com o sufixo `-rejected.yaml`. Elas não alteram o estado calculado da regra.

O documento deve seguir `schema/rule-decision.schema.json` e registrar, no mínimo:

- regra e estados de origem/destino;
- versão constitucional em que a decisão passa a valer;
- motivação;
- impacto e compatibilidade;
- plano de adoção e eventual transição;
- evidências;
- prontidão de enforcement;
- autoridade, data e resultado da decisão.

## Regra de derivação

`scripts/validate_rule_lifecycle.py` começa toda regra em `proposed`, ordena as decisões aprovadas pela versão efetiva e aplica a cadeia de transições. O estado calculado deve ser exatamente igual ao campo `status` da regra publicada.

Isso impede que alguém transforme uma regra em `active`, `deprecated` ou `revoked` apenas editando um YAML sem deixar a decisão correspondente.

## Promoção para active

Uma decisão aprovada para `active` exige `enforcement_readiness.state: ready`.

`ready` não significa necessariamente enforcement automático. Significa que o mecanismo declarado pela própria regra — automático, semiautomático, revisão ou declarativo — está disponível e é suficiente para aplicar a obrigação sem depender de uma promessa futura.

Uma regra com checker parcial, mecanismo ainda indisponível ou lacuna que impeça a aplicação consistente pode permanecer `experimental`, mas não deve ser promovida para `active`.

## Versionamento

`effective_in` não pode apontar para uma versão posterior ao arquivo `VERSION` durante a publicação. Decisões futuras devem entrar junto da versão em que realmente passam a valer.

O validador também rejeita regras cujo `introduced_in` esteja no futuro em relação ao `VERSION` atual.

A classificação da mudança como MAJOR, MINOR ou PATCH continua regida pela Meta-Constituição. Este contrato não reduz essa exigência; ele garante apenas que o estado publicado tenha uma cadeia decisória verificável.

## Escopo do ledger

Os registros de decisão pertencem ao repositório produtor e compõem a trilha de governança. O bundle consumido por projetos continua contendo o estado normativo resultante das regras, enquanto o ledger preserva a proveniência da decisão no repositório canônico.
