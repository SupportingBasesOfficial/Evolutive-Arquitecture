# Semantic relation evidence aggregation

## Propósito

O semantic interpreter pode provar uma relação em uma transformation específica. Isso não significa que todas as ocorrências possíveis daquela relation foram observadas no projeto.

Esta camada agrega fatos semânticos locais comprovados sem convertê-los em claim de coverage.

## Cadeia de confiança

```text
brokered manifest
    ↓
observed provenance
    ↓
producer trust: verified
    ↓
semantic interpretation
    ↓
relation-local evidence aggregation
```

Cada bundle é reexecutado integralmente antes de entrar na agregação. Um interpretation document isolado não é aceito como fonte de confiança.

## Output

A v0.1.0 pode produzir, por exemplo:

```text
relation_id: ffi_native_linkage
has_proven_local_evidence: true
coverage_claim: none
occurrences:
  - transformation-local, hash-bound
```

Cada occurrence preserva:

- digest da semantic interpretation de origem;
- digest da provenance evidence;
- transformation id;
- provenance class;
- interpretation profile;
- inputs e outputs com identity/kind/SHA-256.

## Duplicação e ausência

A mesma semantic interpretation não pode ser agregada duas vezes.

A mesma occurrence `(provenance_evidence_sha256, transformation_id, semantic_relation)` também não pode aparecer duas vezes. Duplicação é erro fail-closed, não aumento de confiança.

A agregação também recusa:

- lista vazia de bundles;
- bundle cuja recomputação não produza nenhum semantic result positivo.

Isso preserva explicitamente:

```text
absence of evidence
!= evidence of absence
```

Um artefato de agregação só existe quando há ao menos uma ocorrência semântica positiva comprovada.

## Authority fence

```yaml
relation_evidence_aggregation_only: true
may_assert_relation_coverage: false
may_assert_complete_rule_semantics: false
may_assert_rule_outcome: false
may_change_rule_status: false
```

Portanto:

```text
has_proven_local_evidence
!= relation covered
!= complete_rule_semantics
!= rule-pass
!= rule activation
```

## Relação com semantic coverage

O evaluator `evolutive.semantic.coverage` v0.1.0 não é alterado por esta etapa. Ele continua avaliando capabilities de adapters e coverage composition.

Uma futura integração entre evidência semântica local e coverage exigirá uma autoridade separada que prove que o mecanismo de observação possui escopo suficiente para afirmar que todas as ocorrências relevantes de uma relation foram vistas. Até lá, a agregação permanece occurrence-local e `coverage_claim: none`.
