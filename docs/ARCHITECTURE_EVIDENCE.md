# Evidência arquitetural portável

## Propósito

A Constituição é agnóstica de linguagem. Portanto, o checker universal não deve tentar interpretar diretamente todas as sintaxes de importação, referência ou composição existentes.

O contrato de evidência arquitetural cria uma representação intermediária canônica entre projetos consumidores, adapters de ecossistema e o checker universal.

## Localização e confiança

A evidência do consumidor, quando presente, fica exclusivamente em:

`.evolutive/architecture-evidence.yaml`

O arquivo segue `schema/architecture-evidence.schema.json`.

O loader rejeita links simbólicos, divergência de versão constitucional, raízes fora do escopo autorizado, raízes de componentes sobrepostas, referências a componentes inexistentes e caminhos de dependência que não pertençam aos componentes declarados.

A árvore `.evolutive` continua fora das raízes de código analisadas. O broker lê o arquivo por uma fronteira dedicada e entrega ao checker somente `graph`; metadados do produtor, coverage, broker audit e a raiz física do projeto não são divulgados ao checker.

## Modelo canônico

Cada componente declara:

- `id`: identidade estável dentro do consumidor;
- `roots`: caminhos que pertencem ao componente;
- `may_depend_on`: componentes para os quais dependências são arquiteturalmente permitidas;
- `public_surface`: globs de caminhos pertencentes à superfície pública.

Cada dependência observada declara origem, destino, caminhos envolvidos e tipo de relação.

Esse modelo não presume Clean Architecture, Hexagonal, DDD, camadas, módulos ES, packages Java ou namespaces .NET. Esses conceitos podem ser projetados sobre o mesmo grafo sem entrar na Constituição universal.

## Proveniência de observação

Evidência manual pode conter apenas produtor + grafo. Quando `producer.kind: adapter`, o envelope também exige `observation`.

`observation` preserva:

- o ecossistema observado;
- coverage reportada pelo adapter (`files_received`, `files_parsed`, `bytes_received`, `unresolved_references`);
- erros estruturados do parser/adapter;
- `broker_audit`, incluindo todos os arquivos considerados, entregues e pulados com motivo;
- `inventory_sha256`, que vincula o inventário autorizado, roots, exclusões e gaps observados;
- `delivered_content_sha256`, que vincula paths, tamanhos e SHA-256 dos conteúdos efetivamente entregues ao adapter;
- `missing_roots` e `skipped_symlinks`, preservando gaps que antes poderiam desaparecer depois da enumeração.

O assembler vincula os números do broker aos números recebidos pelo adapter. Dessa forma, um arquivo rejeitado antes do parser não desaparece da cadeia de evidência e não pode ser esquecido numa futura decisão de cobertura.

Os digests de snapshot permitem que `docs/COVERAGE_ATTESTATION.md` verifique se a evidence corresponde à execução fresca do projeto atual antes de avaliar suficiência.

Esses metadados existem para governança e readiness. Nesta fase, o checker universal continua recebendo somente o grafo, preservando separação de responsabilidades.

## Semântica experimental do checker 0.2.0

Nesta fase o checker usa o grafo apenas para provar violações:

- `ARCH-002`: uma dependência entre componentes gera `fail` quando o destino não está em `may_depend_on` da origem;
- `MOD-001`: uma dependência entre componentes gera `fail` quando `target_path` não pertence à `public_surface` do componente de destino.

Quando nenhuma violação é observada, o resultado permanece `unknown`.

Isso é deliberado. Um grafo parcial, manual ou produzido por um adapter ainda incompleto não pode provar conformidade global pela simples ausência de achados.

## Adapters de ecossistema

Os adapters de referência atuais são:

- `evolutive.python.imports` `0.1.0`, que observa imports Python locais via AST;
- `evolutive.ecmascript.imports` `0.1.0`, que observa referências TypeScript/JavaScript de alta confiança via scanner lexical conservador.

Seus contratos e limites estão documentados em `docs/ECOSYSTEM_ADAPTERS.md`.

Adapters adicionais poderão traduzir evidência específica de Java, C#, Go e outros ecossistemas para o mesmo grafo canônico.

Um adapter não altera o significado das regras nem define a política arquitetural. Ele observa código sob capacidades fechadas e produz fatos no contrato universal; componentes, direção permitida e superfície pública continuam sendo autoridade explícita do consumidor.

A promoção de `ARCH-002` ou `MOD-001` para `active` dependerá de mecanismos capazes de demonstrar cobertura suficiente para sustentar `pass` e `fail`, além dos demais critérios de readiness. A existência de uma coverage attestation `sufficient` ainda não cria esse `pass`; falta uma autoridade de agregação explicitamente governada.
