# Build-time provenance governance

## Propósito

Macros, metaprogramação, generated code, compiler plugins, build graphs e linkers podem introduzir dependências arquiteturais que não existem no source autoral original.

Esta camada torna essas origens **representáveis e auditáveis** sem misturar provenance com semântica da regra.

Ela responde:

> onde e por qual transformação uma referência/dependência apareceu?

Ela não responde sozinha:

> qual relação semântica universal está definitivamente provada?

## Separação de autoridades

```text
source / build inputs
        ↓
provenance observation
        ↓
build-time provenance evidence
        ↓
provenance class
        ↓
partial semantic candidate mapping
        ↓
future semantic observation authority
```

A taxonomia de provenance não pode:

- criar relation semântica;
- declarar taxonomy/profile exaustivo;
- produzir `complete_rule_semantics`;
- produzir `rule-pass`.

## Taxonomia de provenance v1

`governance/build-time-provenance-taxonomy.yaml`

Classes atuais:

- `source_declared`;
- `macro_expansion`;
- `generated_source`;
- `ast_or_ir_transform`;
- `compiler_plugin_injection`;
- `build_graph_binding`;
- `linker_binding`;
- `packaging_or_assembly_binding`.

Cada classe identifica o **estágio de origem** da relação observada, não seu significado arquitetural final.

## Mapeamento semântico parcial

`governance/build-time-semantic-mapping.yaml`

Cada provenance class possui um conjunto fechado de `candidate_relations` que precisam existir na taxonomia semântica atual.

O campo `completeness` é estruturalmente fixado em:

```text
partial
```

Isso é deliberado.

Exemplo:

```text
macro_expansion
    ↓
source_module_dependency
construction_selection
configuration_binding
...
```

significa apenas que essas relações são candidatos coerentes para investigação. Não significa que toda macro se reduz exaustivamente a elas nem que qualquer uma foi provada sem observar o resultado transformado.

## Evidence portável

`schema/build-time-provenance-evidence.schema.json`

Uma evidência registra:

- producer/tool;
- classe de provenance;
- artefatos de input;
- artefatos de output;
- SHA-256 dos artefatos;
- candidate relations;
- se o fato foi `observed` ou apenas `declared`.

O schema não possui `pass`, `rule_outcome` ou `semantic_relation_proven`.

O template canônico está em:

`templates/build-time-provenance-evidence.yaml`

## Binding de artefatos

Inputs e outputs são identificados por:

- identidade estável no contexto do producer;
- tipo de artefato;
- SHA-256.

Isso permite distinguir, por exemplo:

```text
source autoral
    ↓ macro
source expandido
    ↓ compiler transform
IR
    ↓ linker
binary
```

sem assumir que o source original contém todas as dependências do artefato final.

## Fences de autoridade

### Provenance taxonomy

```yaml
authority:
  provenance_only: true
  may_define_semantic_relation: false
  may_assert_semantic_exhaustiveness: false
```

### Semantic mapping

```yaml
authority:
  advisory_mapping_only: true
  may_create_semantic_relation: false
  may_assert_semantic_exhaustiveness: false
```

Esses valores são validados pelo gate canônico.

## Validação

`scripts/validate_build_time_provenance_governance.py` garante:

- schemas válidos;
- VERSION coerente;
- IDs de provenance únicos;
- exatamente um mapping para cada provenance class;
- nenhum mapping para classe inexistente;
- candidate relations existentes na semantic relation taxonomy;
- `completeness: partial` obrigatório;
- fences de autoridade exatos;
- template de evidence válido;
- provenance class do template conhecida;
- candidate relations do template limitadas ao mapping governado.

## Relação com semantic exhaustiveness review

Os reviews atuais de taxonomy, ARCH-002 e MOD-001 identificaram macros, generated code e build-time/linker injection como gaps comuns.

Esta camada reduz esse problema de:

> fenômeno fora do modelo

para:

> fenômeno representável, porém ainda sem producers confiáveis e sem prova de mapeamento semântico completo.

Por isso as reviews continuam corretamente `inconclusive`.

## Próxima fronteira

Para avançar além desta etapa será necessário criar **provenance adapters/producers confiáveis** para ecossistemas concretos, começando por um mecanismo cuja saída possa ser reproduzida sem executar código não confiável do consumidor.

Somente depois poderemos medir se:

1. todos os artefatos derivados relevantes foram observados;
2. toda transformação relevante foi vinculada a inputs/outputs exatos;
3. cada candidate relation pode ser promovida a relação semanticamente comprovada;
4. os gaps atuais de exaustividade foram realmente fechados ou apenas melhor descritos.
