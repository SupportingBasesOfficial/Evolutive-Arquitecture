# Provenance producer trust

## Propósito

A build-time provenance governance separa origem de transformação de semântica arquitetural, mas o evidence bruto continua deliberadamente com:

```text
producer_trust: unverified
```

Isso evita que um producer possa declarar a própria confiabilidade.

Esta camada introduz uma autoridade separada para responder:

> esta implementação específica reproduziu exatamente este evidence sob capacidades fechadas e sem executar código do consumidor?

Ela **não** responde:

> a provenance declarada foi observada de forma independente?

nem:

> uma relação semântica foi comprovada?

## Cadeia de autoridade

```text
consumer declaration
        ↓
authorized artifact bindings
        ↓
provenance producer
        ↓
raw provenance evidence
  producer_trust: unverified
        ↓
independent trust attestor
        ↓
producer trust attestation
  verdict: verified
```

A attestation é separada do evidence bruto. O producer nunca escreve `producer_trust: verified` dentro do próprio output.

## Primeiro producer de referência

Manifesto:

`producers/declared-manifest-verifier.yaml`

Implementação:

`evolutive/provenance/declared_manifest_verifier.py`

Identidade:

```text
evolutive.provenance.declared_manifest_verifier
0.1.0
```

O producer recebe somente:

- uma declaração fechada contendo `constitution_version` e `transformations`;
- uma lista já autorizada de artefatos `{identity, kind, sha256}`.

Campos extras na declaration são recusados. Artifact bindings precisam usar tipos conhecidos e SHA-256 lowercase de 64 hexadecimais.

Ele não recebe project root, não abre arquivos, não acessa rede, não cria subprocessos, não lê environment e não executa código do consumidor.

## O que ele prova

O producer verifica deterministicamente que:

- todos os artefatos declarados existem no conjunto autorizado;
- `kind` e `sha256` batem exatamente;
- todo artifact binding, inclusive não referenciado por uma transformation, possui shape válido;
- transformation IDs não se repetem;
- o producer só trabalha com `observation_basis: declared`;
- o evidence resultante preserva a declaração sem elevar sua autoridade.

Isso permite confiar no producer **como verificador de bindings declarados**.

Não transforma `declared` em `observed`.

## Manifesto fechado

`schema/provenance-producer-manifest.schema.json` fixa:

```yaml
capabilities:
  network: false
  subprocess: false
  environment: false
  executes_consumer_code: false
```

O manifesto também fixa a autoridade:

```yaml
authority:
  may_assert_semantic_relation: false
  may_assert_rule_outcome: false
  may_assert_semantic_exhaustiveness: false
```

A implementação é vinculada pelo `implementation_sha256` canônico.

## Trust attestor independente

A autoridade que emite `verified` também é governada separadamente:

- manifesto: `governance/provenance-producer-trust-attestor.yaml`;
- schema: `schema/provenance-producer-trust-attestor-manifest.schema.json`;
- implementação: `scripts/provenance_producer_trust.py`.

O manifesto do attestor fixa identidade, versão, implementation SHA-256 e autoridade `trust_only`.

Assim, nem o producer nem código de attestation não pinado podem criar confiança por autoafirmação.

## Trust attestation

Contrato:

`schema/provenance-producer-trust-attestation.schema.json`

A função `attest_producer_trust(...)`:

1. valida manifesto e implementation digest do trust attestor;
2. valida manifesto e implementation digest do producer;
3. valida o raw provenance evidence contra taxonomy + semantic mapping canônicos;
4. confirma producer ID/version/kind;
5. normaliza e vincula o conjunto completo de authorized artifact bindings;
6. reexecuta o producer com a mesma declaration e os mesmos bindings;
7. exige igualdade exata entre evidence recebido e evidence reproduzido;
8. emite attestation somente se todas as verificações passarem.

Falha de integridade, capability, identidade ou reprodução gera erro e **nenhuma attestation**.

## Binding completo da attestation

A attestation v1 carrega SHA-256 canônico de:

- declaration completa;
- conjunto completo e normalizado de authorized artifacts;
- raw provenance evidence;
- governance context de build-time provenance;
- producer manifest;
- producer implementation;
- trust attestor manifest;
- trust attestor implementation.

O `governance_context_sha256` cobre explicitamente:

- build-time provenance evidence schema;
- provenance taxonomy;
- provenance → semantic mapping;
- implementação do build-time provenance validator;
- producer manifest schema;
- trust attestation schema;
- trust attestor manifest schema.

Portanto uma mudança de contrato pode invalidar attestations anteriores mesmo quando o Python do producer não mudou.

A attestation ainda registra:

- `observation_basis`;
- `verdict: verified`;
- `reproduced_exactly: true`;
- `capabilities_safe: true`.

Sua autoridade é estritamente:

```yaml
authority:
  trust_only: true
  may_assert_semantic_relation: false
  may_assert_rule_outcome: false
  may_assert_semantic_exhaustiveness: false
```

## Limitação crítica

Para o producer de referência:

```text
observation_basis: declared
```

Portanto:

```text
producer verified
!= provenance independently observed
!= candidate relation proven
!= semantic relation proven
!= complete_rule_semantics
!= rule-pass
```

Essa distinção é necessária para evitar que uma declaração do consumidor ganhe peso semântico apenas porque foi processada por código determinístico.

## Próxima fronteira

O próximo avanço relevante é um producer com `observation_basis: observed` que ainda preserve as mesmas restrições de segurança.

Ele deverá obter fatos de build-time sem executar código não confiável do consumidor — por exemplo, analisando artefatos ou manifests já produzidos e brokerados, com coverage explícita e bindings de snapshot.

Somente então poderemos discutir uma attestation de provenance **observada**, ainda separada de interpretação semântica e de rule outcome.
