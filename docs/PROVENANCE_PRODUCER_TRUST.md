# Provenance producer trust

## Propósito

Raw build-time provenance evidence continua deliberadamente com:

```text
producer_trust: unverified
```

Confiança é emitida somente por uma autoridade separada que reproduz o producer sob capabilities fechadas. Essa confiança nunca implica relação semântica, exaustividade ou rule outcome.

## Producers governados

### Declared manifest verifier

`evolutive.provenance.declared_manifest_verifier` v0.1.0

Recebe declaration fechada + artifact bindings autorizados e comprova apenas que a declaração é reproduzivelmente compatível com esses bindings.

```text
observation_basis: declared
```

### Observed manifest reader

`evolutive.provenance.observed_manifest_reader` v0.1.0

Recebe somente:

- um `build_manifest` brokerado `{identity, kind, sha256, content}`;
- artifact bindings já autorizados;
- o schema canônico do manifest observado.

O producer:

1. recalcula SHA-256 do conteúdo brokerado;
2. exige que identity/kind/SHA correspondam ao binding autorizado;
3. parseia JSON sob schema fechado;
4. exige que todo input/output de cada transformation esteja no scope autorizado com binding exato;
5. emite evidence com `observation_basis: observed`.

Ele não recebe project root, não abre arquivos, não usa rede, subprocess, environment e não executa build, macro, plugin ou código do consumidor.

`observed` significa **observado no artefato brokerado e hash-bound**. Não significa que o producer reconstruiu ou validou universalmente todo o build.

## Authority fence

Todos os producer manifests fixam:

```yaml
network: false
subprocess: false
environment: false
executes_consumer_code: false
```

E:

```yaml
may_assert_semantic_relation: false
may_assert_rule_outcome: false
may_assert_semantic_exhaustiveness: false
```

Raw evidence continua `producer_trust: unverified` mesmo quando `observation_basis: observed`.

## Trust attestor v0.2.0

A autoridade única é:

`evolutive.provenance.producer_trust_attestor` v0.2.0

Ela suporta producers declarativos e observados sem permitir autoatestação.

A attestation usa um subject uniforme:

- `producer_input_sha256` — declaration ou brokered manifest completo;
- `authorized_artifacts_sha256` — conjunto normalizado completo;
- `evidence_sha256`;
- `governance_context_sha256`.

Também vincula:

- producer manifest + implementation SHA-256;
- trust attestor manifest + implementation SHA-256;
- build-time evidence schema;
- observed provenance manifest schema;
- provenance taxonomy;
- provenance → semantic mapping;
- implementação do build-time validator;
- schemas do producer e do próprio attestor.

A attestation só existe depois de reprodução exata do evidence.

## O que `verified + observed` significa

```text
verified producer
+ observation_basis: observed
= o producer reproduziu de forma confiável fatos materializados
  no artefato brokerado e no snapshot autorizado
```

Não significa:

```text
candidate relation proven
semantic relation proven
semantic completeness
rule-pass
```

O evidence observado ainda contém apenas `candidate_relations` e a authority continua `may_assert_semantic_relation: false`.

## Próxima fronteira

Com provenance observada e trust reproduzível, o próximo problema deixa de ser “podemos confiar que o fato foi lido do artefato?” e passa a ser:

> sob quais critérios uma provenance class observada sustenta uma semantic relation específica?

Essa futura autoridade de interpretação semântica deve continuar separada de producer trust, semantic exhaustiveness e rule outcome.
