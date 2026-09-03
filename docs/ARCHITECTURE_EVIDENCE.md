# Evidência arquitetural portável

## Propósito

A Constituição é agnóstica de linguagem. Portanto, o checker universal não deve tentar interpretar diretamente todas as sintaxes de importação, referência ou composição existentes.

O contrato de evidência arquitetural cria uma representação intermediária canônica entre projetos consumidores, adapters de ecossistema e o checker universal.

## Localização e confiança

A evidência do consumidor, quando presente, fica exclusivamente em:

`.evolutive/architecture-evidence.yaml`

O arquivo segue `schema/architecture-evidence.schema.json`.

O loader rejeita links simbólicos, divergência de versão constitucional, raízes fora do escopo autorizado, raízes de componentes sobrepostas, referências a componentes inexistentes e caminhos de dependência que não pertençam aos componentes declarados.

A árvore `.evolutive` continua fora das raízes de código analisadas. O broker lê o arquivo por uma fronteira dedicada e entrega ao checker somente `graph`; metadados do produtor e a raiz física do projeto não são divulgados.

## Modelo canônico

Cada componente declara:

- `id`: identidade estável dentro do consumidor;
- `roots`: caminhos que pertencem ao componente;
- `may_depend_on`: componentes para os quais dependências são arquiteturalmente permitidas;
- `public_surface`: globs de caminhos pertencentes à superfície pública.

Cada dependência observada declara origem, destino, caminhos envolvidos e tipo de relação.

Esse modelo não presume Clean Architecture, Hexagonal, DDD, camadas, módulos ES, packages Java ou namespaces .NET. Esses conceitos podem ser projetados sobre o mesmo grafo sem entrar na Constituição universal.

## Semântica experimental do checker 0.2.0

Nesta fase o checker usa o grafo apenas para provar violações:

- `ARCH-002`: uma dependência entre componentes gera `fail` quando o destino não está em `may_depend_on` da origem;
- `MOD-001`: uma dependência entre componentes gera `fail` quando `target_path` não pertence à `public_surface` do componente de destino.

Quando nenhuma violação é observada, o resultado permanece `unknown`.

Isso é deliberado. Um grafo parcial, manual ou produzido por um adapter ainda incompleto não pode provar conformidade global pela simples ausência de achados.

## Adapters de ecossistema

Adapters futuros poderão traduzir evidência específica de TypeScript, Java, Python, C#, Go e outros ecossistemas para o mesmo grafo canônico.

Um adapter não altera o significado das regras. Ele apenas observa o código e produz evidência no contrato universal.

A promoção de `ARCH-002` ou `MOD-001` para `active` dependerá de mecanismos capazes de demonstrar cobertura suficiente para sustentar `pass` e `fail`, além dos demais critérios de readiness.
