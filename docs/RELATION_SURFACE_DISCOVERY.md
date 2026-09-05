# Relation surface discovery

## Propósito

A relation surface inventory attestation verifica apenas superfícies declaradas pelo consumidor. Ela não consegue detectar uma surface relevante que tenha sido omitida da declaração.

Esta etapa introduz um formato **canônico e discoverable** para `ffi_native_linkage`, permitindo descobrir independentemente da declaration todos os descriptors desse formato que estejam visíveis no inventário autorizado.

## Descriptor canônico v0.1.0

Suffix reservado:

```text
.evolutive-linker-surface.json
```

O descriptor aponta para um `build_manifest` por identity + SHA-256 e declara:

```text
relation_id: ffi_native_linkage
surface_kind: linker_manifest
kind_basis: declared
```

O nome/shape do descriptor é canônico e discoverable. A classificação `linker_manifest` continua declarada; discovery não autentica sua semântica.

## Discovery

O discoverer:

1. reconstrói o inventory autorizado pelo `project-config.yaml`;
2. enumera todos os arquivos cujo path termina no suffix canônico;
3. rejeita descriptor inválido, JSON ambíguo, drift de snapshot, symlink/escape e arquivos acima de 1 MiB;
4. valida o descriptor contra schema fechado;
5. exige que o target esteja no inventory autorizado;
6. rejeita target que seja outro descriptor canônico;
7. exige uma relação 1:1 entre target identity e descriptor — múltiplos descriptors para a mesma target identity falham closed;
8. lê o target com limite de 1 MiB e verifica SHA-256;
9. compara os targets descobertos com a relation surface inventory declaration, quando fornecida;
10. emite `undeclared_targets` para omissões dentro do formato canônico.

Nenhum build, linker, plugin, macro ou código do consumidor é executado.

## Claims permitidos

Quando o inventory autorizado não contém `missing_roots` nem symlinks ignorados:

```text
canonical_descriptor_discovery: complete
```

Se houver qualquer gap de inventory:

```text
canonical_descriptor_discovery: incomplete
```

Isso significa apenas que todos os descriptors com o suffix canônico **dentro do inventory autorizado e observável** foram enumerados e validados.

Portanto:

```text
canonical_descriptor_discovery: complete
!= all linker metadata formats discovered
!= surface kind independently authenticated
!= all relevant project surfaces discovered
!= project relation coverage sufficient
!= complete_rule_semantics
!= rule-pass
```

`project_relation_coverage_claim` permanece estruturalmente fixo em `none`.

## Relação com a declaration

Um target canônico descoberto que não aparece na declaration é reportado em:

```text
undeclared_targets
```

Isso é evidência positiva de uma omissão dentro do formato canônico. Uma lista vazia de `undeclared_targets` não prova que não existam outras superfícies fora desse formato.

Da mesma forma:

```text
zero canonical descriptors discovered
!= zero ffi_native_linkage surfaces in project
```

## Próxima fronteira

Depois de termos discovery canônico + declared inventory alignment, uma futura autoridade poderá avaliar **coverage dentro do domínio canônico**. Coverage global de `ffi_native_linkage` continuará dependendo de uma decisão explícita sobre quais formatos/sources formam uma superfície de observação exaustiva para o projeto.
