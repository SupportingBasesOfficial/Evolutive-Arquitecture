# Execução integrada de conformidade

O comando `scripts/check_project.py` conecta os estágios já existentes sem
fundir suas responsabilidades:

1. valida a configuração e o bundle constitucional;
2. confirma que produtor e consumidor estão em árvores separadas;
3. valida fail-closed o ledger opcional `.evolutive/exceptions/`;
4. deixa o broker selecionar e abrir somente os arquivos autorizados;
5. entrega ao verificador uma requisição fechada, sem caminho da raiz;
6. valida o resultado e produz um relatório único.

## Barreira contra autovalidação

A primeira versão recusa a execução quando o projeto consumidor:

- é o próprio repositório da Constituição;
- está dentro da árvore da Constituição;
- contém a árvore da Constituição.

Essa restrição é deliberadamente conservadora. Ela impede que os testes e o
código interno do validador sejam confundidos com o produto analisado.

## Responsabilidades separadas

- A Constituição publica regras e contratos versionados.
- O projeto consumidor declara suas próprias raízes, exclusões e eventuais exceções.
- O validador de exceções lê somente a área fixa `.evolutive/exceptions/` e nunca entrega esses registros ao checker.
- O broker possui acesso temporário apenas para materializar os arquivos permitidos.
- O verificador recebe somente caminhos relativos, conteúdo autorizado e hashes.
- O relatório registra explicitamente as garantias de isolamento aplicadas.

A configuração e os registros de exceção continuam pertencendo ao consumidor. O
comando não escreve, reorganiza ou injeta arquivos no projeto analisado.

## Exceções do consumidor

Antes da inspeção de código, o comando valida os registros existentes contra
`schema/project-exception.schema.json` e contra o catálogo carregado do bundle
verificado. Qualquer erro encerra a execução antes do checker.

O boundary é fechado:

- `.evolutive` e `.evolutive/exceptions` não podem ser links simbólicos;
- somente arquivos YAML regulares são aceitos no ledger;
- o escopo da exceção deve permanecer dentro das raízes autorizadas;
- o escopo nunca pode apontar para `.evolutive/`;
- uma exceção aprovada só pode referenciar regra que a permita e esteja `active` ou `deprecated`;
- toda exceção deve possuir expiração ou condição de revisão.

Nesta fase, exceções não suprimem automaticamente findings. O comando apenas
garante que qualquer ledger presente seja válido e auditável antes de executar a
inspeção. A semântica de aplicação deve ser definida junto do primeiro enforcement
real de uma regra ativa.

## Contrato do relatório

O arquivo `schema/conformance-report.schema.json` define o relatório completo.
O comando valida o relatório antes de exibi-lo e rejeita campos adicionais,
resultados de verificador inválidos ou alegações falsas de isolamento.

As três garantias não são texto informativo: o schema exige árvores separadas,
raiz não divulgada e entrega exclusiva por meio do broker.

## Cadeia de evidências

Antes de emitir o relatório, o orquestrador compara a quantidade de arquivos e
bytes registrada pelo broker, presente na requisição e declarada pelo verificador.
Qualquer divergência encerra a execução como inválida.

O relatório também inclui:

- SHA-256 da representação canônica da requisição entregue;
- SHA-256 dos bytes exatos do manifesto do verificador.

Esses identificadores permitem demonstrar quais dados e quais capacidades
produziram um resultado, sem incluir a raiz do projeto no contrato do verificador.

## Origem do verificador

O comando integrado aceita somente manifestos localizados na área canônica
`checkers/` do repositório produtor. Um manifesto colocado pelo consumidor,
mesmo que seja sintaticamente válido, é rejeitado.

A versão do manifesto deve ser igual à versão constitucional, e sua lista de
regras deve coincidir com o catálogo carregado do bundle verificado. Todos os
manifestos canônicos também passam pela validação automática do repositório.

## Estado das regras

As regras atuais continuam em estado `proposed`. Por isso, o verificador de
referência devolve `unknown`, e nenhuma reprovação bloqueante é produzida.
