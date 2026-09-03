# Governança de readiness das regras

O ciclo de vida responde **qual é o estado normativo de uma regra**. Readiness responde uma pergunta diferente: **há evidência suficiente para justificar a próxima transição?**

Essas duas coisas não podem ser confundidas. Uma avaliação de readiness não promove uma regra e uma decisão de lifecycle não deve inventar prontidão que não tenha sido avaliada.

## Ledger canônico

Cada regra universal não revogada possui exatamente uma avaliação em:

`assessments/rules/<RULE_ID>.yaml`

O registro segue `schema/rule-readiness.schema.json` e é validado por `scripts/validate_rule_readiness.py`.

O gate exige correspondência exata entre regras e avaliações. Isso impede que novas regras sejam adicionadas sem análise de prontidão e impede que avaliações antigas continuem alegando um status ou nível de enforcement que a regra já não declara.

O `target_status` também precisa ser coerente com o estado avaliado. Em particular, uma regra já `experimental` deve mirar `active`; ela não pode continuar declarando readiness para uma transição que já ocorreu.

## Veredictos

Os veredictos possíveis são:

- `not_ready`: ainda não há base suficiente para a transição avaliada;
- `experimental_ready`: a regra possui escopo e conformidade observáveis e existe um plano de coleta de evidência, mas o enforcement ainda pode possuir lacunas;
- `active_ready`: além dos requisitos experimentais, o mecanismo declarado já está disponível, corresponde ao nível de enforcement da regra e não possui lacunas bloqueantes conhecidas.

`active_ready` não substitui a decisão formal para `active`. Ele apenas permite que uma decisão posterior alegue readiness sem contrariar a evidência registrada.

## Outcomes do checker

O assessment distingue quatro estados de capacidade:

- `unknown_only`: o checker ainda não comprova conformidade nem violação;
- `fail_only`: o checker já comprova algumas violações, mas ausência de finding ainda não prova conformidade;
- `pass_fail`: o mecanismo possui cobertura suficiente para sustentar os dois resultados quando aplicável;
- `not_applicable`: a regra não depende desse tipo de checker.

`fail_only` representa progresso experimental real, mas não é suficiente para `active_ready`.

## Critérios mínimos para experimental

Uma regra só pode receber `experimental_ready` quando:

- o escopo pode ser observado;
- conformidade e violação possuem sinais observáveis;
- existe plano para coletar evidência durante a experimentação;
- a governança de exceções está pronta quando a regra permite exceções.

O mecanismo de enforcement pode permanecer incompleto. Essa é justamente a finalidade do estágio `experimental`: medir aplicabilidade, custo, falsos positivos e lacunas antes de dar força ativa.

## Critérios mínimos para active

`active_ready` exige adicionalmente:

- o enforcement implementado corresponde ao nível declarado na regra;
- o mecanismo necessário está disponível;
- não existem gaps bloqueantes registrados;
- quando a regra depende de checker, o mecanismo deve ser capaz de sustentar `pass` e `fail` com cobertura suficiente, e não apenas `unknown` ou `fail` parcial.

O fato de um mecanismo ser humano ou por revisão não o torna inferior. Para regras com `enforcement.level: review`, readiness ativa exige um protocolo de revisão disponível e capaz de registrar evidência consistente.

## Estado das quatro regras iniciais em 0.2.0

`ARCH-001`, `ARCH-002`, `MOD-001` e `INT-001` estão em `experimental` por decisões de lifecycle efetivas em `0.2.0`.

Os quatro assessments avaliam a próxima fronteira, `active`, e permanecem com `verdict: not_ready`.

A camada de evidência arquitetural portável introduzida durante a experimentação mudou duas avaliações:

- `ARCH-002`: `fail_only`; o checker detecta dependências entre componentes que contrariem `may_depend_on`;
- `MOD-001`: `fail_only`; o checker detecta dependências que alcancem caminhos fora de `public_surface`.

`ARCH-001` continua `unknown_only` e `INT-001` continua `not_applicable` para o checker atual.

Os principais gaps restantes são:

- ainda não existem adapters de ecossistema registrados para produzir o grafo a partir do código com cobertura conhecida;
- ausência de finding no grafo não comprova ausência de dependência no código;
- `ARCH-001` ainda precisa de uma classificação portável de núcleo e detalhes externos;
- `INT-001` ainda precisa de protocolo estruturado de revisão para vazamento de fornecedores.

A promoção para `active` somente poderá ocorrer quando o assessment correspondente demonstrar `active_ready` e uma decisão de lifecycle separada for aprovada com `enforcement_readiness.state: ready`.

## Relação com versionamento

A promoção das quatro regras de `proposed` para `experimental` constitui expansão normativa compatível e inaugura a release MINOR `0.2.0`.

A introdução da representação de evidência e do checker `0.2.0` evolui a ferramenta de experimentação sem alterar o estado normativo das regras nem o bundle constitucional `0.2.0`.
