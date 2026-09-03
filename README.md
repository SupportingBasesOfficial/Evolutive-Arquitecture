# Evolutive-Arquitecture

Constituição arquitetural evolutiva: diretrizes universais, verificáveis e versionadas para orientar decisões de arquitetura e engenharia.

## Estado atual

A Constituição está na versão normativa `0.2.0`. A [Meta-Constituição](./META-CONSTITUTION.md) define como as regras são criadas, interpretadas, aplicadas e evoluídas.

O formato das regras é definido pelo [schema canônico](./schema/rule.schema.json), acompanhado de um [template de autoria](./templates/rule.yaml).

O [ciclo de vida das regras](./docs/RULE_LIFECYCLE.md) torna mudanças de estado auditáveis: qualquer regra que deixe `proposed` deve possuir uma cadeia de decisões aprovada, validada pelo [schema de decisão](./schema/rule-decision.schema.json) e pelo gate canônico.

A [governança de readiness](./docs/RULE_READINESS.md) separa estado normativo de prontidão técnica. Cada regra possui uma avaliação auditável que registra evidências, lacunas e se está apta à próxima transição.

A [governança de exceções](./docs/EXCEPTION_GOVERNANCE.md) define como consumidores registram desvios concretos sem alterar regras universais. Exceções aprovadas só são estruturalmente válidas quando a própria regra as permite, o escopo permanece autorizado e existe expiração ou condição de revisão.

A [governança do próprio repositório](./docs/REPOSITORY_GOVERNANCE.md) declara como `main` deve ser protegida, quais checks são obrigatórios e qual estratégia de merge é normativa. O gate valida o contrato interno e seu vínculo com o CI, sem confundir isso com o enforcement administrativo do GitHub.

O [modelo de adoção](./docs/ADOPTION_MODEL.md) separa o produtor da Constituição, sua ferramenta de validação e os projetos consumidores.

Para adotar a Constituição, um consumidor começa com o [template mínimo de configuração](./templates/project-config.yaml), validado pelo [schema próprio](./schema/project-config.schema.json). Registros opcionais de exceção usam o [schema de exceção](./schema/project-exception.schema.json) e ficam em `.evolutive/exceptions/`.

A [evidência arquitetural portável](./docs/ARCHITECTURE_EVIDENCE.md) define uma representação canônica de componentes, superfícies públicas e dependências observadas. Ela permite que diferentes ecossistemas alimentem o mesmo checker universal sem colocar sintaxe específica dentro da Constituição.

Os [adapters de ecossistema](./docs/ECOSYSTEM_ADAPTERS.md) observam fatos específicos de linguagem sob capacidades fechadas. O consumidor continua sendo a autoridade da política arquitetural; adapters apenas traduzem código para evidência portável. Há adapters de referência para imports Python via AST e para module specifiers TypeScript/JavaScript via scanner lexical conservador, ambos com coverage/ambiguidades auditáveis sem inferir conformidade.

A [coverage attestation](./docs/COVERAGE_ATTESTATION.md) verifica se a evidência é reproduzível no snapshot atual e se a observação é suficientemente completa dentro do escopo exato do manifesto do adapter. Essa camada continua separada do checker: `sufficient` ainda não significa `pass`.

O [motor de conformidade](./docs/CONFORMANCE_ENGINE.md) preserva estágios separados de configuração, confiança, planejamento, inspeção e relatório. A implementação atual já alcança inspeção controlada por broker e execução de verificadores internos, sem entregar livre acesso à raiz do consumidor.

O [broker de escopo](./docs/SCOPE_BROKER.md) enumera somente metadados dentro das raízes autorizadas, ignora links simbólicos e nunca entrega a raiz livre aos verificadores.

O [contrato dos verificadores](./docs/CHECKER_CONTRACT.md) fecha capacidades, entrada e saída. A versão atual aceita somente verificadores internos sem rede, subprocessos ou ambiente.

O [broker de conteúdo](./docs/CONTENT_BROKER.md) é o único componente que abre arquivos autorizados, aplicando extensão, tamanho, UTF-8 e SHA-256 antes de montar a requisição fechada.

O [executor interno](./docs/CHECKER_RUNNER.md) aceita somente verificadores registrados e recebe os arquivos já autorizados, nunca a raiz do projeto consumidor.

O [comando integrado de conformidade](./docs/PROJECT_CHECK.md) mantém produtor e consumidor em árvores separadas, recusa que a Constituição valide a si mesma e emite um relatório validado por schema com cadeia de evidências.

## Primeiras regras universais experimentais

As quatro regras iniciais estão em estado `experimental`. Elas orientam adoção controlada e coleta de evidências, mas ainda não são elegíveis para enforcement bloqueante.

O checker arquitetural `0.2.0` já consegue produzir `fail` comprovável para violações de direção de dependência (`ARCH-002`) e acesso a superfícies internas (`MOD-001`) quando recebe um grafo arquitetural validado. Os adapters de referência Python e ECMAScript produzem esse grafo a partir de relações resolvidas conservadoramente, e a coverage attestation agora consegue distinguir evidence stale/forjada de uma observação reproduzível e suficiente dentro de um manifesto específico. Ainda não existe result aggregator autorizado a converter essa suficiência em `pass`; portanto `ARCH-002` e `MOD-001` continuam `fail_only`/`not_ready`, e nenhuma das quatro regras está `active_ready`.

- [ARCH-001 — Núcleo independente de detalhes externos](./rules/universal/ARCH-001.yaml)
- [ARCH-002 — Dependências apontam para políticas mais estáveis](./rules/universal/ARCH-002.yaml)
- [MOD-001 — Interações entre módulos usam contratos explícitos](./rules/universal/MOD-001.yaml)
- [INT-001 — Tecnologias externas são integradas por adaptadores](./rules/universal/INT-001.yaml)
