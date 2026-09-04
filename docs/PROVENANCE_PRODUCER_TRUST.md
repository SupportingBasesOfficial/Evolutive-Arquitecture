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

- uma declaração estruturada de transformations;
- uma lista já autorizada de artefatos `{identity, kind, sha256}`.

Ele não recebe project root, não abre arquivos, não acessa rede, não cria subprocessos, não lê environment e não executa código do consumidor.

## O que ele prova

O producer verifica deterministicamente que:

- todos os artefatos declarados existem no conjunto autorizado;
- `kind` e `sha256` batem exatamente;
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

## Trust attestation

Contrato:

`schema/provenance-producer-trust-attestation.schema.json`

A função `attest_producer_trust(...)`:

1. valida o manifesto e o implementation digest;
2. valida o raw provenance evidence contra taxonomy + semantic mapping;
3. confirma producer ID/version/kind;
4. reexecuta o producer com a mesma declaration e os mesmos authorized artifact bindings;
5. exige igualdade exata entre evidence recebido e evidence reproduzido;
6. emite attestation somente se todas as verificações passarem.

Falha de integridade, capability, identidade ou reprodução gera erro e **nenhuma attestation**.

## Escopo da attestation

A attestation v1 carrega:

- SHA-256 canônico do evidence;
- producer ID/version;
- implementation SHA-256;
- manifest SHA-256;
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
