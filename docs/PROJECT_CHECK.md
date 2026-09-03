# Execução integrada de conformidade

O comando `scripts/check_project.py` conecta os estágios já existentes sem
fundir suas responsabilidades:

1. valida a configuração e o bundle constitucional;
2. confirma que produtor e consumidor estão em árvores separadas;
3. deixa o broker selecionar e abrir somente os arquivos autorizados;
4. entrega ao verificador uma requisição fechada, sem caminho da raiz;
5. valida o resultado e produz um relatório único.

## Barreira contra autovalidação

A primeira versão recusa a execução quando o projeto consumidor:

- é o próprio repositório da Constituição;
- está dentro da árvore da Constituição;
- contém a árvore da Constituição.

Essa restrição é deliberadamente conservadora. Ela impede que os testes e o
código interno do validador sejam confundidos com o produto analisado.

## Responsabilidades separadas

- A Constituição publica regras e contratos versionados.
- O projeto consumidor declara suas próprias raízes e exclusões.
- O broker possui acesso temporário apenas para materializar os arquivos permitidos.
- O verificador recebe somente caminhos relativos, conteúdo autorizado e hashes.
- O relatório registra explicitamente as garantias de isolamento aplicadas.

A configuração do consumidor continua pertencendo ao consumidor. O comando não
escreve, reorganiza ou injeta arquivos no projeto analisado.

## Contrato do relatório

O arquivo `schema/conformance-report.schema.json` define o relatório completo.
O comando valida o relatório antes de exibi-lo e rejeita campos adicionais,
resultados de verificador inválidos ou alegações falsas de isolamento.

As três garantias não são texto informativo: o schema exige árvores separadas,
raiz não divulgada e entrega exclusiva por meio do broker.

## Estado das regras

As regras atuais continuam em estado `proposed`. Por isso, o verificador de
referência devolve `unknown`, e nenhuma reprovação bloqueante é produzida.
