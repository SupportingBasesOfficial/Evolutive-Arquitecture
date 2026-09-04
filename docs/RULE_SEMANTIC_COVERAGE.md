# Rule semantic coverage

## Propósito

Coverage de arquivos e coverage de adapters não são suficientes para provar a semântica completa de uma regra universal.

Um adapter pode observar perfeitamente todos os imports Python de um snapshot e ainda não observar outras formas de dependência arquitetural, como reflection, dynamic loading, construction/selection, FFI, IPC, configuração externa ou convenções comportamentais.

A camada de **rule semantic coverage** existe para tornar essa diferença explícita e auditável.

Ela responde:

> Quais classes de relação arquitetural a regra exige que sejam observadas, quais delas os mecanismos atuais conseguem observar e quais lacunas ainda impedem uma alegação de semântica completa?

Ela não responde:

> A regra está em conformidade?

## Separação de autoridades

A camada possui quatro autoridades independentes:

1. `governance/semantic-relation-taxonomy.yaml` — catálogo de classes de relação conhecidas;
2. `governance/rule-semantic-profiles.yaml` — mapeia cada regra para relações semanticamente relevantes e para fontes do contrato normativo;
3. `governance/semantic-observation-capabilities.yaml` — declara o que cada adapter realmente observa;
4. `evolutive.semantic.coverage` — combina essas autoridades com alignment e coverage reais do snapshot.

Nenhuma dessas autoridades pode alterar o texto normativo das regras.

A decisão sobre uma futura exaustividade é governada separadamente por `docs/SEMANTIC_EXHAUSTIVENESS_GOVERNANCE.md` e pelo schema `schema/semantic-exhaustiveness-decision.schema.json`.

## Taxonomia inicial

A taxonomia v1 inclui classes conhecidas como:

- `source_module_dependency`;
- `construction_selection`;
- `inheritance_implementation`;
- `direct_call_dependency`;
- `dynamic_runtime_resolution`;
- `configuration_binding`;
- `data_contract_dependency`;
- `ffi_native_linkage`;
- `interprocess_dependency`;
- `behavioral_convention_dependency`.

A taxonomia atual declara:

```yaml
exhaustiveness:
  status: not_established
  decision_reference: null
```

Isso é deliberado. A lista é uma decomposição governada das relações conhecidas, não uma alegação de que toda forma possível de dependência ou interação do universo já foi enumerada.

## Perfis semânticos das regras

Cada profile é vinculado ao contrato normativo atual da regra por SHA-256 canônico do documento YAML parseado.

O profile de `ARCH-002` inclui, entre outras:

- dependência de módulo no source;
- seleção/instanciação de implementação;
- herança/implementação;
- chamada direta;
- resolução dinâmica;
- wiring/configuração;
- contratos de dados;
- FFI/native linkage;
- dependência interprocesso.

O profile de `MOD-001` inclui também `behavioral_convention_dependency`, porque a própria regra declara como falha depender de uma convenção pública não declarada.

Cada relação aponta para um ou mais campos do contrato normativo, por exemplo:

```yaml
normative_sources:
  - statement
  - compliance.pass_conditions[0]
  - compliance.fail_conditions[1]
```

O validator recusa índices inexistentes e recusa profiles cujo digest não corresponde à regra atual.

## Capabilities dos adapters atuais

Os adapters Python e ECMAScript atuais declaram somente:

```text
source_module_dependency
```

com assurance:

```text
complete_when_coverage_sufficient
```

Essa assurance é deliberadamente estreita.

Para Python, ela significa que, quando a coverage attestation é `sufficient`, os import statements dentro do escopo do adapter foram observados de forma suficiente para aquela capability.

Para ECMAScript/TypeScript, ela significa o mesmo para os module specifiers de alta confiança aceitos pelo scanner atual.

Isso **não** significa que o adapter observa:

- reflection;
- FFI;
- IPC;
- runtime service lookup;
- wiring externo;
- todas as chamadas;
- todas as construções;
- convenções comportamentais.

## Cálculo por snapshot

O evaluator reusa duas provas já existentes:

```text
observation alignment
+
coverage composition
```

Para cada relação requerida pelo semantic profile, ele verifica todos os adapters obrigatórios do snapshot.

Uma relação é `covered` somente quando todos os adapters obrigatórios possuem capability compatível e sua coverage individual é `sufficient`.

Se apenas parte dos adapters ou mecanismos satisfaz a relação, ela é `partial`.

Se nenhum mecanismo a observa, ela é `uncovered`.

## Blockers adicionais

Mesmo que uma relação conhecida pareça coberta, semantic completeness continua bloqueada quando existe qualquer uma destas condições:

- taxonomy não exaustiva;
- profile da regra não exaustivo;
- observation alignment incompleto;
- coverage composition incompleta;
- arquivo `unclassified` no scope;
- relation requerida `partial`;
- relation requerida `uncovered`.

## Autoridade do evaluator v0.1.0

O manifesto fixa:

```yaml
authority:
  semantic_coverage_only: true
  may_assert_complete_rule_semantics: false
  may_produce_rule_pass: false
  may_change_rule_status: false
```

O schema de resultado v1 também fixa:

```yaml
complete_rule_semantics: false
```

E não possui `verdict: complete`.

Os únicos verdicts atuais são:

```text
partial
not_proven
```

Portanto nem uma configuração artificial em que todas as relations conhecidas estejam cobertas pode produzir semantic completeness nesta versão.

## Governança de exaustividade

Já existe agora uma autoridade **de governança da decisão**, mas ela não toma a decisão e não muda a autoridade do evaluator.

Uma futura mudança de taxonomy/profile para `established` exige um registro canônico que:

1. preserve snapshot semântico imutável;
2. vincule esse snapshot por SHA-256;
3. registre revisão de todas as dimensões obrigatórias;
4. execute busca adversarial por contraexemplos por múltiplos métodos;
5. preserve os casos encontrados e suas dispositions;
6. apresente múltiplas classes de evidência;
7. não possua gaps ou contraexemplos unresolved quando `approved`;
8. seja referenciado pelo taxonomy/profile no mesmo estado canônico.

O gate também proíbe uma decisão approved “dormente” para o snapshot atual.

Mesmo depois de uma eventual decisão `established`, o semantic coverage evaluator v0.1.0 continuará recusando a alegação até uma evolução contratual separada de sua autoridade.

## Por que a autoridade continua limitada

Permitir `complete_rule_semantics: true` ainda exigirá, no mínimo:

1. taxonomy `established` por decisão aprovada e vinculada ao snapshot correto;
2. profile da regra `established` por decisão aprovada e vinculada ao contrato normativo correto;
3. todos os mecanismos relevantes com capability suficiente para cada relação exigida;
4. discovery/alignment sem superfícies relevantes omitidas;
5. ausência de arquivos ou mecanismos fora da classificação;
6. snapshot e todas as evidências reproduzíveis;
7. evolução explícita do evaluator para possuir autoridade de considerar esses estados;
8. integração posterior com aggregation/readiness sem criar rule-pass implicitamente.

A governança necessária para os itens 1 e 2 existe; as decisões approved e os demais requisitos ainda não.

## Relação com trusted result aggregation

O Trusted Result Aggregator continua autorizado apenas a registrar:

```text
positive_evidence: verified
claim_scope: observed_dependency_graph
```

A semantic coverage layer explica formalmente por que isso continua abaixo de `rule-pass`.

No estado atual, `ARCH-002` e `MOD-001` podem ter `source_module_dependency: covered` em um projeto Python + TypeScript perfeitamente observado, enquanto diversas outras relations continuam `uncovered` e taxonomy/profile continuam `not_established`.

Assim, ausência de finding continua `unknown` do ponto de vista normativo.

## Evolução futura

Uma versão futura poderá adicionar:

- adapters/capabilities para construction e call graphs;
- análise de reflection/dynamic loading;
- FFI/native linkage;
- IPC/event/RPC dependencies;
- data contract relationships;
- configuration/wiring relationships;
- evidence manual ou review-backed para convenções sem representação estrutural;
- revisões formais de exhaustiveness sob a governança já definida.

Somente depois dessas provas uma evolução explícita do contrato poderá sequer considerar `complete_rule_semantics: true`.
