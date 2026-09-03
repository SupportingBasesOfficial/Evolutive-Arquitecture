# Executor de verificadores internos

## Registro fechado

O executor não importa dinamicamente qualquer ponto de entrada declarado por um
arquivo. O manifesto precisa apontar para uma função presente no registro interno
do código.

Um manifesto sintaticamente válido com entrypoint não registrado é rejeitado.

## Validações antes da execução

O executor confirma:

- manifesto e requisição compatíveis com seus schemas;
- identidade do verificador;
- regras solicitadas como subconjunto das regras concedidas;
- coerência entre texto, tamanho em bytes e SHA-256 de cada arquivo;
- ausência de texto quando a capacidade é `none`;
- entrypoint presente no registro interno;
- SHA-256 da representação canônica LF da implementação igual ao digest fixado no manifesto.

A requisição não aceita uma raiz de projeto. O verificador recebe somente os itens
já selecionados e autorizados pelo broker de conteúdo; portanto, não pode descobrir
outros arquivos por meio do contrato.

Depois da execução, confirma:

- resultado compatível com o schema;
- identidade e versão do verificador;
- ausência de regras duplicadas;
- cobertura exata das regras solicitadas.

## Primeiro verificador

`evolutive.checkers.architecture` é um verificador de referência. Como as regras
arquiteturais atuais ainda exigem interpretação semiautomática ou revisão, ele
retorna `unknown` para todas elas.

Isso é intencional: ausência de evidência nunca é convertida em aprovação.

O digest transforma qualquer alteração semântica do código do verificador em uma
mudança explícita de contrato. Conversões de fim de linha do checkout entre LF e
CRLF são normalizadas antes do hash porque o interpretador Python trata esses fins
de linha como equivalentes. Código alterado silenciosamente continua sem poder ser
executado com um manifesto antigo.

## Limite de segurança

O executor atual trabalha apenas com código interno revisado. O registro fechado
reduz a superfície acidental, mas o processo Python continua tendo as permissões
do processo hospedeiro. Plugins externos continuam proibidos até existir sandbox.
