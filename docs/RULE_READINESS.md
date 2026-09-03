# Governança de readiness das regras

O ciclo de vida responde **qual é o estado normativo de uma regra**. Readiness responde uma pergunta diferente: **há evidência suficiente para justificar a próxima transição?**

Essas duas coisas não podem ser confundidas. Uma avaliação de readiness não promove uma regra e uma decisão de lifecycle não deve inventar prontidão que não tenha sido avaliada.

## Ledger canônico

Cada regra universal não revogada possui exatamente uma avaliação em:

`assessments/rules/<RULE_ID>.yaml`

O registro segue `schema/rule-readiness.schema.json` e é validado por `scripts/validate_rule_readiness.py`.

O gate exige correspondência exata entre regras e avaliações. Isso impede que novas regras sejam adicionadas sem análise de prontidão e impede que avaliações antigas continuem alegando um status ou nível de enforcement que a regra já não declara.

## Veredictos

Os veredictos possíveis são:

- `not_ready`: ainda não há base suficiente para a transição avaliada;
- `experimental_ready`: a regra possui escopo e conformidade observáveis e existe um plano de coleta de evidência, mas o enforcement ainda pode possuir lacunas;
- `active_ready`: além dos requisitos experimentais, o mecanismo declarado já está disponível, corresponde ao nível de enforcement da regra e não possui lacunas bloqueantes conhecidas.

`active_ready` não substitui a decisão formal para `active`. Ele apenas permite que uma decisão posterior alegue readiness sem contrariar a evidência registrada.

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
- uma regra dependente de checker não pode alegar readiness ativa se o único resultado disponível for `unknown`.

O fato de um mecanismo ser humano ou por revisão não o torna inferior. Para regras com `enforcement.level: review`, readiness ativa exige um protocolo de revisão disponível e capaz de registrar evidência consistente.

## Estado das quatro regras iniciais

Nesta fase, `ARCH-001`, `ARCH-002`, `MOD-001` e `INT-001` foram avaliadas como `experimental_ready`.

Nenhuma foi classificada `active_ready`.

Os principais gaps observados são:

- o checker arquitetural de referência ainda retorna `unknown` e não detecta violações;
- ainda não existe representação portável de fronteiras arquiteturais, módulos e superfícies públicas;
- ainda não existe protocolo estruturado de revisão para vazamento de fornecedores;
- a classificação de núcleo, estabilidade e responsabilidade arquitetural ainda precisa ser tornada observável para os mecanismos semiautomáticos.

Isso é uma conclusão de engenharia, não um bloqueio de roadmap: a próxima release pode levar as regras a `experimental`, mas ativação normativa deverá esperar o fechamento dos gaps correspondentes.

## Relação com versionamento

A versão `0.1.0` da Meta-Constituição declara que ainda não estabelece regras universais. Portanto, a primeira promoção das regras iniciais para `experimental` representa expansão normativa compatível e deve ocorrer em uma release MINOR, prevista como `0.2.0`, acompanhada das decisões de lifecycle e dos artefatos/checksums correspondentes.

Esta fase de readiness não altera `VERSION`, status de regra nem bundle constitucional.
