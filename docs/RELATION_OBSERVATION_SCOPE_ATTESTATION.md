# Relation observation scope attestation

## Propósito

A semantic relation evidence aggregation prova ocorrência local positiva, mas não prova que todos os artefatos relevantes do projeto foram observados.

Esta camada introduz uma autoridade separada para atestar completude **somente dentro de um conjunto fechado e explicitamente declarado de brokered manifests**.

## Escopo v0.1.0

A primeira versão é deliberadamente limitada a:

```text
scope_type: brokered_manifest_set
relation_id: ffi_native_linkage
```

O scope declaration contém a lista exata de manifests por `identity + sha256`.

## Cadeia

```text
closed brokered manifest set
        ↓
trusted observed provenance bundles
        ↓
fresh semantic interpretation
        ↓
proven local relation aggregation
        ↓
relation observation scope attestation
```

## Estados

### Integridade quebrada

Bundle adulterado, trust inválido, semantic interpretation que não reproduz ou aggregation que não corresponde aos bundles positivos encerram o processo com erro fail-closed.

Isso não é `scope_coverage: incomplete`; é ausência de base confiável para qualquer attestation.

### Scope incomplete

Quando os inputs são confiáveis, mas o conjunto `identity + sha256` dos bundles fornecidos diverge do scope declarado:

```text
scope_coverage: incomplete
```

### Scope complete

Somente quando:

- o scope declarado corresponde exatamente ao conjunto de brokered manifests fornecidos;
- todos os bundles são reprocessáveis de forma fresca;
- todas as semantic interpretations positivas estão na aggregation;
- todas as occurrences positivas estão preservadas.

Então:

```text
scope_coverage: complete
```

## Authority fence

```yaml
scope_attestation_only: true
may_assert_scope_completeness: true
may_assert_project_relation_coverage: false
may_assert_complete_rule_semantics: false
may_assert_rule_outcome: false
may_change_rule_status: false
```

Portanto:

```text
scope_coverage: complete
!= project relation covered
!= complete_rule_semantics
!= rule-pass
!= rule activation
```

O campo `project_relation_coverage_claim` permanece estruturalmente fixo em `none`.

## Ausência de evidência

A v0.1.0 exige ao menos uma semantic interpretation positiva para emitir attestation. Um scope sem evidência positiva não pode ser convertido em claim negativo.

```text
absence of evidence
!= evidence of absence
```

Uma futura autoridade de project-level relation coverage precisará provar, separadamente, que o conjunto fechado de manifests é suficiente para representar todas as superfícies relevantes onde aquela relation poderia surgir.
