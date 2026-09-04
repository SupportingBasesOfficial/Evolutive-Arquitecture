# Relation surface inventory attestation

## Propósito

A relation observation scope attestation prova completude dentro de um conjunto fechado de brokered manifests. Ela não prova que o consumidor declarou todas as superfícies do projeto onde `ffi_native_linkage` poderia surgir.

Esta etapa cria uma autoridade separada para verificar se as **superfícies declaradas** existem no inventário autorizado e estão hash-bound ao conteúdo atual.

## Escopo v0.1.0

A primeira versão é deliberadamente limitada a:

```text
relation_id: ffi_native_linkage
surface_kind: linker_manifest
```

Cada surface declarada contém:

- `identity`: path POSIX relativo e canônico;
- `surface_kind: linker_manifest`;
- `sha256`: digest do arquivo esperado.

Paths absolutos, `..`, backslashes, identities duplicadas e shapes adicionais são rejeitados.

## Verificação

O attestor reconstrói o inventário autorizado a partir do `project-config.yaml` e verifica:

1. ausência de missing roots e symlinks ignorados no inventário autorizado;
2. presença de cada surface declarada dentro do inventário autorizado;
3. arquivo regular, não symlink e confinado ao project root;
4. `size_bytes` ainda igual ao snapshot do inventário antes da leitura;
5. limite local de 1 MiB por surface;
6. estabilidade do tamanho durante a leitura;
7. SHA-256 do conteúdo atual igual ao declarado.

Uma divergência entre `size_bytes` inventariado e o arquivo lido produz `surface_snapshot_mismatch`; o attestor não atravessa silenciosamente drift entre inventory e content verification.

Nenhum build, linker, plugin, macro ou código do consumidor é executado.

## Resultado

Quando todos os critérios fecham:

```text
declared_surface_inventory: aligned
```

Caso contrário:

```text
declared_surface_inventory: misaligned
```

A declaração é canonicalizada por `(identity, sha256)` antes de ser hash-bound, portanto a ordem da lista não altera sua identidade semântica.

## Authority fence

```yaml
inventory_attestation_only: true
may_assert_declared_surface_inventory_alignment: true
may_assert_project_relation_coverage: false
may_assert_complete_rule_semantics: false
may_assert_rule_outcome: false
may_change_rule_status: false
```

Portanto:

```text
declared_surface_inventory: aligned
!= all relevant project surfaces declared
!= project relation coverage sufficient
!= complete_rule_semantics
!= rule-pass
!= rule activation
```

O campo `project_relation_coverage_claim` permanece estruturalmente fixo em `none`.

## Próxima fronteira

Uma futura autoridade de **relation surface discovery/completeness** precisará demonstrar, independentemente da declaração do consumidor, se existem superfícies relevantes não declaradas. Somente depois disso um project-level relation coverage evaluator poderá considerar um verdict positivo.
