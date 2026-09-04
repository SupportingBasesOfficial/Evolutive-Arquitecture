# Provenance semantic interpretation

## Propósito

Build-time provenance e producer trust provam que um fato foi materializado em um artefato brokerado e reproduzido por um producer confiável. Isso ainda não transforma `candidate_relations` em relações semânticas comprovadas.

Esta camada introduz uma autoridade separada e mínima para interpretar casos explicitamente governados.

## Primeira interpretação autorizada

A v0.1.0 autoriza somente:

```text
provenance_class: linker_binding
candidate relation: ffi_native_linkage
observation_basis: observed
trust verdict: verified
producer: evolutive.provenance.observed_manifest_reader
```

Resultado:

```text
semantic_relation: ffi_native_linkage
verdict: proven
scope: transformation_local
```

A evidência positiva inclui os `inputs` e `outputs` exatos da transformation, com identity/kind/SHA-256.

## Cadeia de confiança

```text
brokered build manifest
        ↓
observed provenance producer
        ↓
raw provenance evidence
        ↓
producer trust attestation: verified
        ↓
semantic interpretation policy
        ↓
transformation-local semantic evidence
```

O interpreter revalida a trust attestation por reprodução fresca antes de emitir qualquer relação semântica.

## Authority fence

O manifesto `governance/provenance-semantic-interpreter.yaml` permite somente interpretação semântica local.

```yaml
semantic_interpretation_only: true
may_assert_semantic_relation: true
may_assert_rule_outcome: false
may_assert_semantic_exhaustiveness: false
may_assert_complete_rule_semantics: false
```

Portanto:

```text
semantic relation proven
!= relation coverage complete
!= taxonomy/profile exhaustive
!= complete_rule_semantics
!= rule-pass
!= rule activation
```

## Fail closed

Nenhuma heurística ou fallback é permitido. Se não existir profile exato para `(provenance_class, semantic_relation)`, o resultado positivo simplesmente não é emitido.

A v0.1.0 também exige:

- `observation_basis: observed`;
- trust attestation `verified` reproduzida de forma fresca;
- producer observado canônico;
- relation presente no mapping de provenance;
- relation existente na taxonomy semântica;
- interpretação `direct`;
- scope `transformation_local`.

## Escopo atual

Outras candidates — como `configuration_binding`, `data_contract_dependency`, `direct_call_dependency` ou relações derivadas de generated source/macros — permanecem não autorizadas para promoção positiva.

O objetivo desta etapa é demonstrar uma cadeia positiva segura e auditável para uma única relação, não generalizar semântica antes de existir evidência suficiente.
