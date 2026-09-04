# Trusted result aggregation

## Propósito

O checker arquitetural atual é deliberadamente `fail_only`: ele consegue provar violações, mas ausência de finding permanece `unknown`.

Trusted result aggregation adiciona uma autoridade separada capaz de produzir um resultado positivo **derivado** somente quando a cadeia de evidências necessária é reproduzível e explicitamente autorizada por uma positive result policy.

O aggregator não altera o resultado original do checker e não muda o status normativo de nenhuma regra.

## Cadeia de confiança

Para cada execução, o aggregator regenera:

1. observation alignment no snapshot atual;
2. coverage composition no mesmo inventário;
3. architecture evidence fresca para cada adapter obrigatório;
4. coverage attestation fresca para cada evidence;
5. checker result fresco sobre o grafo de cada evidence.

O resultado agregado é vinculado aos digests de:

- inventory;
- ecosystem catalog;
- observation policy;
- positive result policy;
- observation alignment;
- coverage composition;
- attestations individuais;
- findings individuais.

## Precedência de `fail`

Qualquer checker observation `fail` produz `fail` agregado para aquela regra.

Coverage incompleta, alignment incompleto ou ausência de positive profile nunca escondem uma violação comprovada.

## Positive result policy

`governance/positive-result-policy.yaml` é a autoridade que define quais regras podem receber `pass` derivado e sob quais condições.

A versão inicial autoriza somente:

- `ARCH-002`;
- `MOD-001`.

Ambas exigem:

- checker source status `unknown` em todas as observations frescas;
- observation alignment `aligned`;
- coverage composition `complete`;
- zero arquivos `unclassified` dentro do scope positivo.

Regras sem profile permanecem `unknown`, mesmo quando não possuem findings.

## Semântica dos outcomes

### `fail`

Significa que pelo menos uma execução fresca do checker encontrou uma violação comprovável.

`basis: checker_fail`

### `pass`

Significa que a regra possui positive profile explícito e todas as condições de derivação positiva foram satisfeitas no snapshot atual.

`basis: positive_derivation`

Esse `pass` é um **resultado de conformidade derivado**. Ele não altera o checker source result e não promove a regra para `active`.

### `unknown`

Permanece o fallback seguro quando:

- a regra não possui positive profile;
- alignment está incompleto;
- coverage composition está incompleta;
- existem arquivos unclassified quando o profile exige zero;
- o checker source status não corresponde ao status autorizado para derivação positiva.

## Separação de autoridades

O manifesto `governance/result-aggregator.yaml` fixa:

- `aggregation_only: true`;
- `may_mutate_checker_result: false`;
- `may_produce_derived_pass: true`;
- `may_change_rule_status: false`.

Assim, a autoridade que deriva conformidade positiva não possui autoridade para reescrever o checker nem para alterar lifecycle/readiness normativo.

## Por que zero unclassified nesta versão

Ecosystem discovery é `catalog_scope_only`. Um arquivo fora do catálogo pode ser irrelevante, mas também pode representar uma superfície de código ainda desconhecida.

A primeira positive result policy prefere segurança: enquanto houver arquivo unclassified dentro do scope positivo, o resultado permanece `unknown`.

Consumidores podem definir `scope.roots` e exclusões para que o scope arquitetural contenha apenas superfícies efetivamente governadas.

## Multi-ecossistema

Cada adapter obrigatório é avaliado separadamente sobre evidence fresca. Um finding em qualquer observation é suficiente para `fail`.

`pass` exige que todas as observations declaradas e detectadas satisfaçam os gates de alignment e coverage no mesmo inventário.

## Limitações atuais

Trusted result aggregation fecha a lacuna técnica entre `fail_only` e um resultado positivo auditável, mas ainda não torna as regras prontas para enforcement universal.

Permanecem, entre outras, estas limitações:

- adapters positivos existem apenas para Python e ECMAScript/TypeScript sem JSX;
- superfícies conhecidas sem adapter mantêm o resultado `unknown`;
- o catálogo não prova conhecimento semântico de todo formato possível;
- o aggregator ainda não está integrado ao comando/relatório final de adoção como mecanismo de enforcement;
- lifecycle/readiness de regra permanece uma decisão separada.

Por isso ARCH-002 e MOD-001 continuam `experimental` e `not_ready` nesta etapa.
