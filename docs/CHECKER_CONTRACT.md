# Contrato dos verificadores

## Princípio

Um verificador recebe dados; ele não recebe autoridade para procurar dados.

A requisição não contém a raiz do projeto, caminhos absolutos, credenciais,
variáveis de ambiente ou acesso a serviços. Campos desconhecidos são rejeitados.

## Manifesto

O manifesto declara antecipadamente:

- ID e versão do verificador;
- versão da Constituição para a qual aquele manifesto foi registrado;
- regras que ele sabe avaliar;
- ponto de entrada interno;
- necessidade de conteúdo;
- extensões aceitas;
- tamanho máximo por arquivo;
- capacidades proibidas.

`version` identifica a versão do checker e deve corresponder a `checker_version`
do resultado produzido pela implementação. `constitution_version` é uma dimensão
separada: identifica a versão constitucional exata cuja combinação de regras e
contrato foi autorizada para aquele manifesto. Um novo release da Constituição não
muda artificialmente a versão do checker se a implementação do checker não mudou.

Na versão 1 do manifesto, somente o runtime `builtin` é aceito. Rede, subprocessos
e ambiente são obrigatoriamente `false`.

O template é apenas um exemplo estrutural. Ele não registra nem executa o
verificador descrito.

## Requisição

O motor construirá uma requisição contendo apenas:

- ID do verificador;
- IDs das regras selecionadas;
- caminhos relativos previamente autorizados;
- tamanho e SHA-256 de cada entrada;
- texto, somente quando concedido pelo manifesto.

Não existe campo `project_root`.

## Resultado

Cada regra produz um resultado `pass`, `fail`, `not_applicable` ou
`unknown`. Violações devem trazer mensagem, caminho relativo e fingerprint
estável; linha e coluna são opcionais.

O resultado também declara quantos arquivos e bytes foram recebidos. Erros da
ferramenta são separados de violações arquiteturais.

## Limite de segurança

Schemas impedem concessões acidentais pela interface, mas não contêm código hostil.
Enquanto não houver sandbox, apenas verificadores internos e revisados serão
aceitos. A introdução de um runtime externo exigirá nova versão do contrato.
