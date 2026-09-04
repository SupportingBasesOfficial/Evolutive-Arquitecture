# Semantic exhaustiveness review evidence

## Propósito

A governança de exaustividade semântica define **como uma decisão pode ser tomada**, mas uma decisão confiável precisa de material de revisão separado, reproduzível e auditável.

Esta camada responde:

> qual evidência sustenta, rejeita ou ainda deixa inconclusiva uma alegação de exaustividade para o snapshot semântico atual?

Ela não responde:

> o taxonomy/profile está estabelecido?

A decisão continua sendo uma autoridade separada em `decisions/semantic-exhaustiveness/**`.

## Separação entre review e decision

A cadeia é:

```text
semantic taxonomy/profile
        ↓
semantic snapshot
        ↓
review evidence package
        ↓
supports_established | supports_rejection | inconclusive
        ↓
separate governed decision
        ↓
established | not_established
```

O pacote de review **não altera status**, não cria `decision_reference` e não produz `complete_rule_semantics` ou `rule-pass`.

## Schema

O contrato canônico é:

`schema/semantic-exhaustiveness-review-evidence.schema.json`

Cada pacote contém:

- versão da review;
- versão da Constituição;
- subject (`taxonomy` ou `rule_profile`);
- `semantic_content_sha256`;
- snapshot semântico completo;
- avaliação das dez dimensões obrigatórias;
- counterexamples adversariais;
- evidências;
- gaps residuais;
- conclusão da revisão.

## Conclusões possíveis

### `supports_established`

Só é válido quando:

- todas as dimensões estão `supported`;
- não existem residual gaps;
- não existem counterexamples `potential_gap` ou `confirmed_gap`;
- existem ao menos duas classes independentes de evidência.

Mesmo assim, isso ainda é **review evidence**, não uma decisão `approved`.

### `supports_rejection`

Exige ao menos:

- uma dimensão `unsupported`; ou
- um counterexample `confirmed_gap`.

Isso fornece material para uma decisão `rejected`, mas não cria a decisão automaticamente.

### `inconclusive`

Exige incerteza explícita:

- dimensão `inconclusive`; ou
- counterexample `potential_gap`; ou
- residual gap.

Esse é o estado atual dos três subjects revisados.

## Binding ao snapshot

Os pacotes usam o mesmo snapshot semântico da governança de decisão.

### Taxonomy

O snapshot contém:

- `taxonomy_version`;
- `constitution_version`;
- `relations`.

### Rule profile

O snapshot contém:

- `profile_version`;
- `constitution_version`;
- `rule_id`;
- `rule_contract_sha256`;
- `relations`.

O validator recalcula o SHA-256 canônico e exige igualdade com `semantic_content_sha256`.

Além disso, um pacote current-review só é válido se seu snapshot for **idêntico ao taxonomy/profile atual**. Qualquer mudança semântica torna a review antiga stale e o gate falha fechado até existir novo pacote.

## Caminhos canônicos

Taxonomy:

```text
evidence/semantic-exhaustiveness/taxonomy/<semantic_content_sha256>-review.yaml
```

Rule profile:

```text
evidence/semantic-exhaustiveness/rules/<RULE_ID>/<semantic_content_sha256>-review.yaml
```

Existe exatamente um pacote current-review por subject atual.

## Revisão atual da taxonomy

Conclusão:

```text
inconclusive
```

A taxonomia já representa explicitamente:

- source/module dependency;
- construction/selection;
- inheritance/implementation;
- direct calls;
- dynamic runtime resolution;
- configuration/wiring;
- data contracts;
- FFI/native linkage;
- interprocess dependencies;
- behavioral conventions.

A revisão adversarial, porém, preservou como potenciais gaps:

1. macros/metaprogramação/code generation que injetam referências em compile/build time;
2. build-time linkage que não se enquadre inequivocamente como configuration binding, source dependency ou FFI/native linkage;
3. ausência de uma matriz transversal capaz de demonstrar que futuras famílias normativas não exigem uma classe adicional.

Por isso a taxonomy continua `not_established`.

## Revisão atual de ARCH-002

Conclusão:

```text
inconclusive
```

A análise indica que o profile atual cobre diretamente o texto normativo conhecido de ARCH-002 e está vinculado ao SHA-256 do contrato da regra.

Os principais gaps residuais são:

- decidir se `behavioral_convention_dependency` é necessária para ARCH-002 ou sempre redutível às classes já presentes;
- provar como macros, generated code e build-time linkage se enquadram sem perda semântica.

Nenhuma decisão de exaustividade foi criada.

## Revisão atual de MOD-001

Conclusão:

```text
inconclusive
```

O profile atual cobre inclusive `behavioral_convention_dependency`, diretamente relacionada à condição de falha por convenção pública não declarada.

O gap principal continua sendo provar, cross-ecosystem, que generated-code access e transformações de build são sempre representáveis pelas relations atuais.

Nenhuma decisão de exaustividade foi criada.

## Relação com semantic coverage

Review evidence e runtime semantic coverage respondem perguntas diferentes.

Review evidence:

> a decomposição semântica parece exaustiva?

Semantic coverage:

> os mecanismos atuais observam todas as relations requeridas neste snapshot?

Mesmo que uma futura review conclua `supports_established`, ainda será necessário:

- uma decisão approved governada;
- taxonomy/profile `established` no mesmo estado canônico;
- capabilities suficientes para todas as relations;
- evolução explícita do semantic coverage evaluator, que hoje proíbe `complete_rule_semantics=true`;
- revisão posterior do trusted result aggregator e readiness.

## Gate canônico

`scripts/validate_semantic_exhaustiveness_review_evidence.py` valida:

- schema;
- SHA do snapshot;
- path canônico;
- subject conhecido;
- igualdade com o snapshot semântico atual;
- unicidade das referências de evidência;
- unicidade dos counterexample IDs;
- relation IDs válidos;
- requisitos específicos de cada conclusão;
- presença de exatamente um current-review package por subject atual.

O validator é chamado pelo gate canônico em `scripts/validate_repository.py`.

## Próxima fronteira

O resultado atual não pede uma aprovação; ele direciona a pesquisa.

A próxima etapa correta é investigar formalmente os gaps comuns aos três pacotes:

1. macros e metaprogramação;
2. compile-time/build-time code generation;
3. linker/build graph dependency injection;
4. transformação de source/AST antes do artefato executável;
5. ecossistemas em que dependências arquiteturais surgem fora do source textual convencional.

Somente depois dessa pesquisa a review deve ser atualizada para `supports_established`, `supports_rejection` ou permanecer `inconclusive` com gaps mais precisos.
