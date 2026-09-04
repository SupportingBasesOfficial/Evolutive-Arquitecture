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

Uma decisão de exaustividade não altera a regra normativa, não altera checker outcome, não produz `rule-pass`, não promove lifecycle e não torna o mecanismo `active_ready` por si só.

## Conteúdo semântico e SHA-256

Uma decisão não usa o SHA do arquivo YAML inteiro, porque o próprio arquivo contém `status`, `rationale` e `decision_reference`, o que criaria auto-referência criptográfica.

O gate calcula um snapshot semântico imutável.

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

O `semantic_content_sha256` da decisão é o SHA-256 da representação JSON canônica desse snapshot. Assim, a decisão preserva historicamente exatamente o conteúdo analisado sem depender dos metadados que registram o resultado da própria decisão.

## Registro de decisão

O schema canônico é `schema/semantic-exhaustiveness-decision.schema.json`.

Cada registro contém:

- `sequence` monotônica por subject;
- subject (`taxonomy` ou `rule_profile`);
- id do subject;
- SHA-256 do conteúdo semântico;
- snapshot completo revisado;
- dimensões obrigatórias de análise;
- busca adversarial por contraexemplos;
- evidências;
- gaps não resolvidos;
- outcome `approved` ou `rejected`;
- autoridade, data e rationale;
- `supersedes` quando não for a primeira decisão do subject.

## Caminhos canônicos

Taxonomy:

```text
decisions/semantic-exhaustiveness/taxonomy/<sequence>-<semantic_content_sha256>-<outcome>.yaml
```

Rule profile:

```text
decisions/semantic-exhaustiveness/rules/<RULE_ID>/<sequence>-<semantic_content_sha256>-<outcome>.yaml
```

O caminho faz parte da validação. Um registro equivalente em outro nome não é considerado canônico.

## História linear e reversível

Cada subject possui uma cadeia própria e linear:

```text
sequence 1 -> sequence 2 -> sequence 3 -> ...
```

As regras são:

- sequences começam obrigatoriamente em `1`;
- não pode haver saltos;
- não pode haver sequence duplicada no mesmo subject;
- `sequence: 1` exige `supersedes: null`;
- toda decisão `N > 1` precisa superseder exatamente a decisão `N - 1` do mesmo subject;
- somente a maior sequence do subject é a decisão efetiva.

Isso permite, por exemplo:

```text
1-approved -> 2-rejected -> 3-approved
```

sem reescrever ou apagar qualquer decisão histórica. O mesmo snapshot pode ser reavaliado depois de novas evidências porque a identidade histórica não depende apenas do digest e do outcome: a sequence também faz parte do caminho.

A estrutura linear elimina forks, múltiplas decisões efetivas e ciclos por construção.

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

Uma decisão `rejected` é válida e deve ser preservada como histórico. Ela pode documentar gaps descobertos, contraexemplos não resolvidos, dimensões ainda não revisadas ou evidência insuficiente.

Uma rejeição efetiva nunca sustenta `status: established`. Uma aprovação antiga que já foi superseded também deixa de ter autoridade sobre o estado atual.

## Histórico sobrevive à evolução da Constituição

Um registro histórico preserva a `constitution_version` sob a qual foi decidido.

O gate exige que a versão da decisão seja a mesma do snapshot preservado e que o digest corresponda àquele snapshot. Ele **não** exige que toda decisão histórica use a `VERSION` atual do repositório.

Assim, uma futura mudança `0.2.0 -> 0.3.0` não invalida retroativamente decisões tomadas e verificadas em `0.2.0`.

Quando uma decisão sustenta o estado atual, a correspondência com a versão atual ocorre naturalmente porque o snapshot da taxonomy/profile atual precisa ser idêntico ao snapshot aprovado.

## Vínculo com o estado atual

Os schemas de taxonomy/profile aplicam:

```text
not_established -> decision_reference: null
established     -> decision_reference: <effective approved canonical path>
```

Para `established`, a decisão referenciada precisa:

- existir;
- ser a decisão efetiva, isto é, a maior sequence daquele subject;
- ser `approved`;
- apontar para o mesmo subject;
- possuir o mesmo `semantic_content_sha256`;
- carregar snapshot idêntico ao conteúdo semântico atual.

## Aprovação dormente é proibida

Uma decisão **efetiva** `approved` para o snapshot atual não pode permanecer no repositório enquanto taxonomy/profile continua `not_established`.

A decisão e a mudança de status precisam entrar no mesmo estado canônico. Isso impede guardar uma aprovação atual para ativação posterior sem novo gate.

Aprovações históricas superseded ou aprovações relativas a snapshots antigos continuam preservadas e não possuem autoridade corrente.

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
- caminhos canônicos sequenciados;
- digests dos snapshots;
- preservação da versão histórica;
- requisitos de decisões approved;
- sequence única e contígua `1..N` por subject;
- predecessor exato em `supersedes`;
- decisão efetiva única por subject;
- coerência do taxonomy atual;
- coerência de cada rule profile atual;
- ausência de aprovações efetivas dormentes para snapshots correntes.

O validator é executado por `scripts/validate_repository.py` em todo gate de integração/publicação.

## Próxima fronteira

Somente depois desta governança existir faz sentido executar uma revisão formal e adversarial da própria taxonomia/profile.

Mesmo que uma futura revisão conclua `established`, ainda será necessário, separadamente:

1. aumentar as capabilities dos adapters até cobrir todas as relações requeridas;
2. evoluir o semantic coverage evaluator sob nova autoridade para aceitar uma alegação de semântica completa;
3. integrar essa prova ao result aggregator;
4. revisar readiness;
5. somente então avaliar qualquer mudança de lifecycle/enforcement.
