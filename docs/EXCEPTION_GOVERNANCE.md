# Governança de exceções

Exceções pertencem ao projeto consumidor, não ao catálogo constitucional. A Constituição define quando uma regra admite exceção e quais condições devem ser respeitadas; o consumidor registra o caso concreto sem modificar a regra universal.

## Local canônico

Os registros ficam exclusivamente em:

`.evolutive/exceptions/<EXCEPTION_ID>.yaml`

O diretório é governança do consumidor e permanece fora do conteúdo entregue aos checkers porque `.evolutive/**` continua excluído do escopo de código.

## Contrato

Cada registro segue `schema/project-exception.schema.json` e deve declarar:

- ID estável da exceção;
- regra afetada e versão constitucional;
- contexto e justificativa;
- responsável;
- riscos aceitos;
- controles compensatórios;
- evidência de atendimento às condições de exceção previstas pela própria regra;
- escopo limitado a caminhos autorizados;
- expiração ou condição objetiva de revisão;
- decisão, autoridade e data.

O template de autoria é `templates/project-exception.yaml`.

## Regra de aprovação

Uma exceção aprovada só é válida estruturalmente quando:

- a regra existe no bundle constitucional verificado;
- a versão registrada é exatamente a versão fixada pelo consumidor;
- a regra declara `exceptions.allowed: true`;
- a regra está `active` ou `deprecated`;
- o escopo permanece dentro das raízes autorizadas do projeto;
- o escopo não aponta para `.evolutive/`;
- existe `expires_on` ou `review_condition`.

Uma solicitação rejeitada pode ser preservada como histórico mesmo quando a regra não admite exceções, porque ela não altera a conformidade.

## Boundary de confiança

O validador não percorre livremente o projeto. Ele abre somente o diretório fixo `.evolutive/exceptions/`, recusa links simbólicos, subdiretórios e arquivos não YAML, e valida cada registro contra o catálogo obtido do bundle já verificado por checksum.

Registros de exceção nunca são entregues ao checker. Eles pertencem à camada de governança/orquestração, separada da inspeção de código.

## Sem exceções permanentes implícitas

Um registro sem expiração e sem condição de revisão é inválido. Se o mesmo desvio precisar ser renovado repetidamente, isso é sinal para revisar a regra, sua condição de exceção ou a arquitetura do consumidor, em vez de transformar a exceção em política permanente.

## Estado desta fase

Esta fase fecha o contrato, a validação e a propriedade dos registros. Ela não promove nenhuma regra atual nem transforma uma exceção em mecanismo automático de supressão de findings. A semântica de aplicação de exceções a resultados de enforcement deve permanecer explícita e só pode ser adicionada junto da primeira regra efetivamente ativa.
