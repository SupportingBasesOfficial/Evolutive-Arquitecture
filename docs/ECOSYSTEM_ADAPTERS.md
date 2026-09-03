# Adapters de ecossistema

## Propósito

A Constituição permanece agnóstica de linguagem. Adapters de ecossistema existem para observar fatos específicos de uma linguagem ou plataforma e traduzi-los para contratos portáveis consumidos pelo checker universal.

Um adapter **não define a arquitetura**. Ele não escolhe módulos, não decide a direção permitida das dependências e não declara superfície pública. Essas decisões pertencem à política arquitetural do consumidor.

## Separação de autoridades

O fluxo seguro é:

1. o consumidor declara `.evolutive/architecture-policy.yaml`;
2. o policy validator confirma primeiro o `config.yaml` e depois versão, escopo, roots, superfícies e referências da política;
3. o adapter broker entrega ao adapter somente arquivos autorizados e a política validada;
4. o adapter observa fatos do ecossistema e retorna `dependencies`, `coverage` e `errors`;
5. o assembler vincula política, resultado e `broker_audit` em `architecture-evidence.yaml`;
6. o checker universal avalia as regras sobre o grafo portável.

`scripts/generate_architecture_evidence.py` materializa esse caminho ponta a ponta e é a entrada preferida para geração automática.

O adapter nunca recebe a raiz física do projeto e não possui rede, subprocessos ou ambiente.

## Manifesto e registry

Cada adapter interno possui manifesto em `adapters/*.yaml`, validado por `schema/adapter-manifest.schema.json`.

O manifesto fixa:

- identidade e versão do adapter;
- versão constitucional compatível;
- ecossistema observado;
- entrypoint interno registrado;
- SHA-256 canônico da implementação;
- extensões aceitas e limite por arquivo;
- proibição de rede, subprocessos e ambiente.

O gate compara o conjunto completo de manifestos com o registry interno e rejeita ids, entrypoints ou implementações sem correspondência. O checksum da implementação também é recalculado com normalização de line endings.

A versão do adapter e a versão da Constituição são autoridades independentes. Um adapter só muda de versão quando sua implementação ou semântica muda.

## Request

`schema/adapter-request.schema.json` limita a entrada a:

- identidade do adapter;
- versão constitucional;
- componentes da política validada;
- arquivos brokerados com path relativo, tamanho, SHA-256 e texto.

Não existe campo para `project_root`.

## Result e coverage

`schema/adapter-result.schema.json` exige:

- dependências observadas;
- quantidade de arquivos recebidos e analisados;
- bytes recebidos;
- número de referências locais não resolvidas;
- erros estruturados, como falhas lexicais ou de parsing.

Coverage é evidência, não decoração. Uma execução com erros ou referências não resolvidas não pode futuramente ser usada para provar conformidade global.

Além do resultado do adapter, a evidência preserva o `broker_audit`. Isso mantém auditáveis arquivos considerados mas não entregues ao adapter, por exemplo por extensão, limite de tamanho ou conteúdo não UTF-8. O assembler exige que `files_delivered`/`bytes_read` do broker coincidam com `files_received`/`bytes_received` do adapter. Assim um skip anterior ao parser/scanner não desaparece da cadeia de cobertura.

## Adapter Python de referência

`evolutive.python.imports` usa o AST da biblioteca padrão do Python. Ele não usa regex para interpretar imports.

A versão `0.1.0`:

- aceita somente `.py`;
- constrói um índice de módulos locais a partir dos component roots declarados;
- resolve apenas imports locais que apontem de forma única para arquivos brokerados;
- ignora dependências externas ao projeto;
- registra referências locais ambíguas ou não resolvidas em coverage;
- transforma somente dependências entre componentes em edges canônicos;
- nunca cria uma dependência por aproximação.

O adapter é deliberadamente conservador. Recursos Python cujo destino não possa ser determinado com segurança permanecem não resolvidos.

## Adapter ECMAScript de referência

`evolutive.ecmascript.imports` cobre TypeScript e JavaScript sem introduzir Node, npm ou TypeScript compiler dentro da fronteira confiável.

A versão `0.1.0` aceita `.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`, `.mjs` e `.cjs`. Ela usa um scanner lexical limitado ao reconhecimento de module specifiers e observa:

- `import '...'`;
- `import ... from '...'`;
- `export ... from '...'`;
- `import('...')` quando o specifier é literal;
- `require('...')` quando o specifier é literal.

Somente specifiers relativos `./` e `../` são resolvidos automaticamente. O resolver aceita alvo com extensão explícita ou um único candidato por extensão suportada/`index.*`. Se houver zero ou mais de um candidato, a referência permanece não resolvida.

Bare specifiers como `react`, `@scope/pkg` ou `@app/core` são registrados como incerteza de coverage porque, sem autoridade adicional de `package.json`, `tsconfig paths`, package exports ou runtime, o adapter não pode distinguir pacote externo de alias local com segurança.

Comentários e conteúdo textual não são tratados como imports. Falhas lexicais reduzem `files_parsed` e geram `LEX_ERROR`; o adapter não tenta reparar ou inferir dependências a partir de entrada que não conseguiu analisar com segurança.

## Evolução

Os adapters Python e ECMAScript demonstram que o contrato portável suporta dois modelos de resolução diferentes sem alterar o checker universal ou o significado das regras.

Adapters futuros para Java, C#, Go e outros ecossistemas devem implementar o mesmo contrato. A existência de dois adapters de referência ainda não implica readiness universal. A promoção das regras depende de coverage conhecida, comportamento reproduzível, falsos positivos controlados e capacidade suficiente nos ecossistemas declarados como suportados.
