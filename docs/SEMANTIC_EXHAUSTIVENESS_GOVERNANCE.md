# Governança de exaustividade semântica

## Propósito

A rule semantic coverage consegue responder quais classes de relação arquitetural estão `covered`, `partial` ou `uncovered`, mas isso não prova que a própria lista de classes seja completa.

Esta governança responde a uma pergunta diferente:

> quais condições precisam ser satisfeitas antes que uma taxonomia ou um profile semântico possa ser declarado `established` quanto à exaustividade?

A resposta é deliberadamente mais forte que um campo booleano. `established` exige uma decisão auditável, vinculada ao conteúdo semântico exato que foi revisado.

## Separação de autoridades

Há quatro autoridades distintas:

1. a regra normativa define o que deve ser verdadeiro;
2. taxonomy/profile decompõem a semântica conhecida em classes de relação;
3. semantic coverage mede quais dessas classes os mecanismos atuais conseguem observar;
4. semantic exhaustiveness governance controla se a decomposição pode ser considerada exaustiva.

Uma decisão de exaustividade:

- não altera a regra normativa;
- não altera checker outcome;
- não produz `rule-pass`;
- não promove a regra no lifecycle;
- não torna o mecanismo `active_ready` por si só.

## Conteúdo semântico e SHA-256

Uma decisão não usa o SHA do arquivo YAML inteiro, porque o próprio arquivo contém `status`, `rationale` e `decision_reference`, o que criaria auto-referência criptográfica.

Em vez disso, o gate calcula um snapshot semântico imutável.

### Taxonomy snapshot

Inclui somente:

- `taxonomy_version`;
- `constitution_version`;
- `relations`.

### Rule profile snapshot

Inclui somente:

- `profile_version`;
- `constitution_version`;
- `rule_id`;
- `rule_contract_sha256`;
- `relations`.

O `semantic_content_sha256` da decisão é o SHA-256 da representação JSON canônica desse snapshot.

Assim, a decisão pode preservar historicamente exatamente o conteúdo que foi analisado sem depender dos metadados que registram o resultado da própria decisão.

## Registro de decisão

O schema canônico é `schema/semantic-exhaustiveness-decision.schema.json`.

Cada registro contém:

- subject (`taxonomy` ou `rule_profile`);
- id do subject;
- SHA-256 do conteúdo semântico;
- snapshot completo revisado;
- dimensões obrigatórias de análise;
- busca adversarial por contraexemplos;
- evidências;
- gaps não resolvidos;
- outcome `approved` ou `rejected`;
- autoridade, data e rationale.

## Caminhos canônicos

Taxonomy:

```text
decisions/semantic-exhaustiveness/taxonomy/<semantic_content_sha256>-<outcome>.yaml
```

Rule profile:

```text
decisions/semantic-exhaustiveness/rules/<RULE_ID>/<semantic_content_sha256>-<outcome>.yaml
```

O caminho faz parte da validação. Um registro equivalente em outro nome não é considerado canônico.

## Requisitos para `approved`

Uma decisão `approved` só é válida quando:

- todas as dimensões obrigatórias de revisão estão `true`;
- busca adversarial por contraexemplos foi executada;
- pelo menos dois métodos distintos de busca foram usados;
- não existem `unresolved_gaps`;
- nenhum contraexemplo permanece com disposition `unresolved`;
- existem ao menos duas classes distintas de evidência;
- referências de evidência não são duplicadas;
- snapshot, subject e digest são coerentes;
- o caminho do registro é canônico.

Isso não demonstra matematicamente que nenhum contraexemplo poderá existir. Ele estabelece o nível mínimo de governança necessário para aceitar uma alegação de exaustividade dentro da Constituição.

## Rejeições são preservadas

Uma decisão `rejected` é válida e deve ser preservada como histórico.

Ela pode documentar:

- gaps descobertos;
- contraexemplos não resolvidos;
- dimensões ainda não revisadas;
- evidência insuficiente.

Uma rejeição nunca sustenta `status: established`.

## Vínculo com o estado atual

Os schemas de taxonomy/profile aplicam a seguinte regra:

```text
not_established -> decision_reference: null
established     -> decision_reference: <approved canonical path>
```

Além disso, o gate verifica o conteúdo referenciado.

Para `established`, a decisão precisa:

- existir;
- ser `approved`;
- apontar para o mesmo subject;
- possuir o mesmo `semantic_content_sha256`;
- carregar snapshot idêntico ao conteúdo semântico atual.

## Aprovação dormente é proibida

Uma decisão `approved` para o snapshot **atual** não pode permanecer no repositório enquanto o taxonomy/profile continua `not_established`.

A decisão e a mudança de status devem entrar no mesmo estado canônico.

Isso evita que uma aprovação antiga seja ativada posteriormente sem que o gate reavalie o vínculo exato entre decisão e contrato.

Decisões approved históricas sobre snapshots antigos podem permanecer preservadas.

## `supersedes`

Uma decisão pode apontar para uma decisão anterior por `supersedes`.

O alvo precisa:

- existir no repositório;
- estar dentro de `decisions/semantic-exhaustiveness/`;
- ser diferente da própria decisão.

Isso permite manter uma cadeia auditável quando uma nova análise substitui uma decisão anterior.

## Estado atual

Nesta versão:

- taxonomy continua `not_established`;
- profiles de ARCH-002/MOD-001 continuam `not_established`;
- não existe decisão `approved` para o snapshot atual;
- `complete_rule_semantics` continua estruturalmente `false`;
- o semantic coverage evaluator v0.1.0 continua recusando taxonomy/profile `established`;
- não existe autoridade de `rule-pass`.

Portanto este mecanismo cria **a governança para uma futura decisão**, mas não toma essa decisão.

## Gate canônico

`scripts/validate_semantic_exhaustiveness_governance.py` valida:

- schemas;
- todos os registros de decisão;
- caminhos canônicos;
- digests dos snapshots;
- requisitos adicionais de decisões approved;
- vínculos de `supersedes`;
- coerência do taxonomy atual;
- coerência de cada rule profile atual;
- ausência de aprovações dormentes para snapshots correntes.

O validator é executado por `scripts/validate_repository.py` em todo gate de integração/publicação.

## Próxima fronteira

Somente depois desta governança existir faz sentido executar uma revisão formal e adversarial da própria taxonomia/profile.

Mesmo que uma futura revisão conclua `established`, ainda será necessário, separadamente:

1. aumentar as capabilities dos adapters até cobrir todas as relações requeridas;
2. evoluir o semantic coverage evaluator sob nova autoridade para aceitar uma alegação de semântica completa;
3. integrar essa prova ao result aggregator;
4. revisar readiness;
5. somente então avaliar qualquer mudança de lifecycle/enforcement.
