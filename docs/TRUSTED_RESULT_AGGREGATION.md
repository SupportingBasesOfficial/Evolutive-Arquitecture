# Trusted result aggregation

## Propósito

O checker arquitetural atual é deliberadamente `fail_only`: ele consegue provar violações, mas ausência de finding permanece `unknown`.

Trusted result aggregation adiciona uma autoridade separada para responder uma pergunta mais limitada e auditável:

> existe evidência positiva reproduzível de que o grafo de dependências observado, dentro do scope técnico coberto pelos adapters atuais, não contém as violações verificadas por este checker?

A resposta positiva é registrada como `positive_evidence: verified`.

Ela **não** transforma o status normativo da regra em conformidade positiva nesta versão. O status permanece `unknown` quando não existe `fail` comprovado.

## Por que positive evidence não é rule pass

ARCH-002 e MOD-001 são regras universais. Os adapters atuais observam relações específicas:

- Python: imports resolvidos conservadoramente;
- ECMAScript/TypeScript sem JSX: module specifiers resolvidos conservadoramente.

Mesmo com coverage `sufficient`, isso prova completude dentro do mecanismo observado, não que toda forma semanticamente possível de dependência arquitetural foi capturada. Dependências dinâmicas, FFI, IPC, reflection e outros mecanismos podem existir fora desse grafo observado.

Por isso a positive result policy fixa:

- `claim_scope: observed_dependency_graph`;
- `complete_rule_semantics: false`.

Enquanto `complete_rule_semantics` não puder ser provado por um contrato futuro específico da regra, o aggregator v0.1.0 não possui autoridade para produzir conformidade normativa positiva.

## Cadeia de confiança

Para cada execução, o aggregator regenera:

1. observation alignment no snapshot atual;
2. coverage composition no mesmo inventário;
3. architecture evidence fresca para cada adapter obrigatório;
4. coverage attestation fresca para cada evidence;
5. checker result fresco sobre o grafo de cada evidence.

Além disso, cada attestation regenerada deve corresponder **exatamente** à attestation usada pela coverage composition:

- mesmo adapter id + versão;
- mesmo `attestation_sha256`;
- mesmo coverage verdict.

Se essa identidade divergir, a agregação falha fechado. Isso impede combinar composition e checker observations produzidas sobre momentos ou conteúdos diferentes.

## Provenance

O resultado agregado é vinculado aos digests de:

- inventory;
- ecosystem catalog;
- observation policy;
- positive result policy;
- observation alignment;
- coverage composition;
- attestations individuais;
- findings individuais.

Alterações no snapshot invalidam um resultado antigo por recomputação determinística.

## Precedência de `fail`

Qualquer checker observation `fail` produz `status: fail` agregado para aquela regra.

Coverage incompleta, alignment incompleto, ausência de profile ou limites semânticos nunca escondem uma violação comprovada.

## Positive result policy

`governance/positive-result-policy.yaml` define quais regras podem receber evidência positiva verificada e sob quais condições.

A versão inicial possui profiles somente para:

- `ARCH-002`;
- `MOD-001`.

Ambos exigem:

- checker source status `unknown` em todas as observations frescas;
- observation alignment `aligned`;
- coverage composition `complete`;
- zero arquivos `unclassified` dentro do scope positivo;
- claim restrito a `observed_dependency_graph`;
- `complete_rule_semantics: false`.

Regras sem profile permanecem `positive_evidence: not_authorized`.

## Semântica dos outcomes

### Violação comprovada

```text
status: fail
positive_evidence: insufficient
basis: checker_fail
```

Significa que pelo menos uma execução fresca do checker encontrou uma violação comprovável.

### Evidência positiva verificada no grafo observado

```text
status: unknown
positive_evidence: verified
basis: positive_evidence_verified
claim_scope: observed_dependency_graph
complete_rule_semantics: false
```

Significa que todas as condições do positive profile foram satisfeitas no snapshot atual, mas a evidência ainda não prova a semântica universal completa da regra.

### Evidência positiva insuficiente

```text
status: unknown
positive_evidence: insufficient
basis: insufficient_positive_evidence
```

Ocorre quando, por exemplo:

- alignment está incompleto;
- coverage composition está incompleta;
- existem arquivos unclassified;
- o checker source status diverge do permitido pelo profile.

### Regra sem profile positivo

```text
status: unknown
positive_evidence: not_authorized
basis: no_positive_profile
```

Ausência de profile nunca é interpretada como conformidade.

## Separação de autoridades

O manifesto `governance/result-aggregator.yaml` fixa:

- `aggregation_only: true`;
- `may_mutate_checker_result: false`;
- `may_produce_positive_evidence: true`;
- `may_produce_rule_pass: false`;
- `may_change_rule_status: false`.

A autoridade que compõe evidências, portanto, não pode:

- reescrever o checker source result;
- produzir conformidade normativa positiva;
- alterar lifecycle ou readiness normativo.

## Por que zero unclassified nesta versão

Ecosystem discovery é `catalog_scope_only`. Um arquivo fora do catálogo pode ser irrelevante, mas também pode representar uma superfície de código ainda desconhecida.

Enquanto houver arquivo unclassified dentro do scope positivo, o profile não recebe positive evidence verificada.

Consumidores podem definir `scope.roots` e exclusões para que o scope arquitetural contenha apenas superfícies efetivamente governadas.

## Multi-ecossistema

Cada adapter obrigatório é avaliado separadamente sobre evidence fresca. Um finding em qualquer observation é suficiente para `fail`.

Positive evidence só pode ser `verified` quando todas as observations exigidas satisfazem alignment, coverage e identidade de attestation sobre o mesmo inventário.

## O que seria necessário para rule pass no futuro

Uma futura evolução de autoridade só poderá considerar conformidade normativa positiva quando houver, no mínimo:

1. um profile específico da regra capaz de provar `complete_rule_semantics: true`;
2. mecanismos de observação que cubram todas as formas relevantes de dependência previstas pela regra naquele scope;
3. governança explícita dessa transição de autoridade;
4. schemas e testes que continuem fail-closed diante de lacunas semânticas;
5. revisão separada de readiness/lifecycle.

Isso exigirá evolução contratual explícita; não poderá acontecer silenciosamente dentro do aggregator v0.1.0.

## Limitações atuais

Permanecem, entre outras:

- observação positiva implementada apenas para Python e ECMAScript/TypeScript sem JSX;
- superfícies conhecidas sem adapter impedem positive evidence verificada;
- o catálogo não prova conhecimento semântico de todo formato possível;
- o grafo observado não representa necessariamente toda forma de dependência da regra universal;
- o resultado agregado ainda não está integrado ao comando/relatório final de adoção como mecanismo de enforcement;
- lifecycle/readiness de regra continua separado.

Por isso ARCH-002 e MOD-001 permanecem `experimental`, `fail_only` e `not_ready` nesta etapa.
