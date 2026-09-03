# Adapters de ecossistema

## Propósito

A Constituição permanece agnóstica de linguagem. Adapters de ecossistema existem para observar fatos específicos de uma linguagem ou plataforma e traduzi-los para contratos portáveis consumidos pelo checker universal.

Um adapter **não define a arquitetura**. Ele não escolhe módulos, não decide a direção permitida das dependências e não declara superfície pública. Essas decisões pertencem à política arquitetural do consumidor.

## Separação de autoridades

O fluxo é:

1. o consumidor declara `.evolutive/architecture-policy.yaml`;
2. o policy validator confirma versão, escopo, roots, superfícies e referências;
3. o adapter broker entrega ao adapter somente arquivos autorizados e a política validada;
4. o adapter observa fatos do ecossistema e retorna `dependencies`, `coverage` e `errors`;
5. o assembler combina política + observações em `architecture-evidence.yaml`;
6. o checker universal avalia as regras sobre o grafo portável.

O adapter nunca recebe a raiz física do projeto e não possui rede, subprocessos ou ambiente.

## Manifesto

Cada adapter interno possui manifesto validado por `schema/adapter-manifest.schema.json`.

O manifesto fixa:

- identidade e versão do adapter;
- versão constitucional compatível;
- ecossistema observado;
- entrypoint interno registrado;
- SHA-256 canônico da implementação;
- extensões aceitas e limite por arquivo;
- proibição de rede, subprocessos e ambiente.

A versão do adapter e a versão da Constituição são autoridades independentes. Um adapter só muda de versão quando sua implementação ou semântica muda.

## Request

`schema/adapter-request.schema.json` limita a entrada a:

- identidade do adapter;
- versão constitucional;
- componentes da política validada;
- arquivos brokerados com path relativo, tamanho, SHA-256 e texto.

Não existe campo para `project_root`.

## Result

`schema/adapter-result.schema.json` exige:

- dependências observadas;
- quantidade de arquivos recebidos e analisados;
- bytes recebidos;
- número de referências locais não resolvidas;
- erros estruturados, como falhas de parsing.

Coverage é evidência, não decoração. Uma execução com parse errors ou referências não resolvidas não pode futuramente ser usada para provar conformidade global.

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

## Evolução

Adapters futuros para TypeScript, Java, C#, Go e outros ecossistemas devem implementar o mesmo contrato, sem alterar o significado das regras universais.

A existência de um adapter para um ecossistema não implica readiness universal. A promoção das regras depende de coverage conhecida, comportamento reproduzível, falsos positivos controlados e capacidade suficiente nos ecossistemas declarados como suportados.
