# Coverage composition

## Propósito

Coverage attestation responde se uma observação individual é suficientemente completa dentro do escopo técnico de um adapter específico.

Coverage composition responde uma pergunta diferente:

> todas as observações que o consumidor declarou como obrigatórias para esta análise arquitetural estão suficientemente cobertas no mesmo snapshot?

Ela não responde se todos os ecossistemas existentes no projeto foram descobertos e não altera resultados de regra.

## Observation policy

O consumidor declara a matriz obrigatória em:

`.evolutive/observation-policy.yaml`

O arquivo segue `schema/observation-policy.schema.json` e contém:

- versão da policy;
- versão constitucional;
- adapters obrigatórios por id e versão.

A policy é deliberadamente explícita. A versão `0.1.0` do composer não possui autoridade de ecosystem discovery. Portanto, omitir um ecossistema relevante da policy não pode ser interpretado como prova de que ele não existe.

## Cadeia de autoridade

A composição confiável é:

1. project config define o scope autorizado;
2. architecture policy define componentes e fronteiras;
3. observation policy declara quais adapters são obrigatórios;
4. cada adapter obrigatório gera evidence fresca;
5. cada evidence recebe coverage attestation fresca;
6. todas as attestations devem estar vinculadas ao mesmo `inventory_sha256`;
7. o coverage composer produz `complete` ou `incomplete`.

O composer não aceita uma coleção arbitrária de attestations externas como verdade. Ele regenera a cadeia evidence + attestation para cada adapter exigido pela policy.

## Semântica de `complete`

`evaluation.verdict: complete` significa somente:

> todas as observações listadas na observation policy atual receberam coverage attestation `sufficient` sobre o mesmo inventário autorizado.

Não significa:

- que todos os ecossistemas presentes no projeto foram descobertos;
- que toda semântica dinâmica de uma linguagem foi observada;
- que uma regra está em conformidade;
- que o checker produziu `pass`;
- que uma regra pode ser promovida para `active`.

O output registra `scope.basis: declared_observation_policy` justamente para manter essa limitação explícita e verificável.

## Semântica de `incomplete`

`evaluation.verdict: incomplete` ocorre quando pelo menos uma observação obrigatória possui coverage attestation `insufficient`.

Falhas de integridade, manifesto, versão, policy ou divergência de snapshot não são tratadas como simples incompletude: interrompem a composição como erro.

## Mesmo snapshot

Todos os adapters obrigatórios devem operar sobre o mesmo inventário autorizado. O composer compara `inventory_sha256` entre as attestations.

O digest de conteúdo entregue pode variar entre adapters, porque cada manifesto aceita extensões diferentes. O inventário, porém, deve ser o mesmo.

## Autoridade do composer

O manifesto canônico `governance/coverage-composer.yaml` limita a autoridade da implementação:

- `composition_only: true`;
- `may_change_checker_outcome: false`;
- `ecosystem_discovery: false`.

A implementação é vinculada por SHA-256 canônico e o gate rejeita drift entre manifesto, schema e código.

## Relação com o checker

Coverage composition não entra no checker request e não modifica findings.

Nesta fase a cadeia permanece:

`checker result` + `coverage composition`

como duas evidências independentes.

Uma futura autoridade de result aggregation poderá definir, sob contrato próprio, quando essas evidências podem ser combinadas. Esse mecanismo não existe nesta versão.

## Limitação deliberada: descoberta de ecossistema

A observation policy é uma declaração de autoridade do consumidor, não uma prova automática de completude global do projeto.

Antes de usar `complete` como parte de uma futura prova positiva de conformidade, será necessário resolver pelo menos uma destas estratégias de forma governada:

- ecosystem discovery confiável;
- declaração de ecossistemas com evidência independente;
- matriz de coverage derivada por uma autoridade separada;
- outro mecanismo que prove que a observation policy não omite superfícies relevantes.

Até lá, `complete` continua restrito à matriz declarada.
