# Ecosystem discovery e observation alignment

## Propósito

Coverage composition responde se todas as observações declaradas pelo consumidor estão suficientemente cobertas no mesmo inventário. Ainda faltava responder uma pergunta anterior:

> a observation policy declarou todas as superfícies de código conhecidas que aparecem no snapshot autorizado?

Este mecanismo adiciona duas autoridades separadas:

1. **ecosystem discoverer** — identifica superfícies de código conhecidas por um catálogo governado;
2. **observation aligner** — compara essas superfícies com a observation policy do consumidor.

Nenhuma das duas altera findings ou outcomes do checker.

## Catálogo governado

`governance/ecosystem-catalog.yaml` é a autoridade de classificação desta versão.

Cada superfície declara:

- id estável;
- ecossistema;
- extensões reconhecidas;
- adapter canônico obrigatório quando já existe cobertura;
- `observation: null` quando a superfície é conhecida, mas ainda não existe adapter autorizado.

A versão inicial reconhece:

- Python;
- ECMAScript/TypeScript sem JSX;
- JSX/TSX como superfície conhecida ainda sem cobertura;
- Java;
- Kotlin;
- .NET (C#/F#/VB);
- Go;
- Rust;
- Swift;
- PHP;
- Ruby;
- C/C++.

Adicionar ou alterar uma superfície é mudança de governança e passa pelo gate canônico.

## Ecosystem inventory

O discoverer usa somente o inventário metadata-only já produzido pelo `scope_broker`.

Ele não abre conteúdo dos arquivos.

O resultado é vinculado por:

- `inventory_sha256` — mesmo digest canônico usado pelos brokers de adapter;
- `catalog_sha256` — versão exata do catálogo usado na classificação;
- id, versão e implementation SHA-256 do discoverer.

Cada superfície detectada registra:

- `surface_id`;
- ecossistema;
- extensões efetivamente observadas;
- quantidade de arquivos;
- digest determinístico dos paths;
- observation/adapter correspondente, quando existe.

## Arquivos não classificados

Arquivos cuja extensão não está no catálogo aparecem em `unclassified_files`.

Eles **não são considerados irrelevantes por certeza**. A única afirmação feita é que estão fora do escopo classificatório do catálogo atual.

Por isso todo resultado carrega:

`scope.catalog_scope_only: true`

Essa limitação impede interpretar discovery como prova semântica universal sobre qualquer linguagem ou formato possível.

## Observation alignment

O aligner regenera o ecosystem inventory do snapshot atual e carrega a observation policy atual.

Ele deriva:

- `required_observations` — adapters exigidos pelas superfícies detectadas e suportadas;
- `declared_observations` — adapters declarados pelo consumidor;
- `missing_observations` — adapters exigidos pelo discovery, mas omitidos na policy;
- `unsupported_surfaces` — superfícies conhecidas detectadas sem adapter disponível;
- `unclassified_files` — arquivos fora do catálogo.

### `aligned`

`aligned` significa somente:

> dentro do catálogo governado atual, toda superfície detectada que possui adapter está declarada na observation policy e nenhuma superfície conhecida sem adapter foi encontrada.

Não significa:

- conformidade de regra;
- coverage suficiente dos adapters;
- `pass`;
- que todo formato de código imaginável está catalogado;
- que arquivos unclassified são irrelevantes.

### `incomplete`

O alignment é `incomplete` quando:

- uma observation requerida foi omitida (`missing_required_observation`); ou
- uma superfície conhecida sem adapter foi detectada (`unsupported_detected_surface`).

Alterações no snapshot, catálogo ou observation policy invalidam um alignment antigo porque a validação é feita por recomputação determinística.

## Relação com coverage composition

Depois desta camada, a prova de coverage pode ser lida em duas dimensões independentes:

1. **observation alignment** — a policy cobre as superfícies conhecidas detectadas pelo catálogo?
2. **coverage composition** — todas as observations declaradas produziram attestations `sufficient` no mesmo inventário?

Nenhuma dessas evidências, isolada ou combinada nesta versão, produz outcome positivo de regra.

## Limites atuais

Ainda permanecem dois limites estruturais antes de qualquer `unknown -> pass`:

1. o catálogo é governado e extensível, mas não prova que conhece todo formato de código possível;
2. ainda não existe result aggregator autorizado a combinar checker result + alignment + coverage composition em um outcome positivo.

Esses limites permanecem explícitos no readiness das regras experimentais.
