# Broker de conteúdo

## Responsabilidade exclusiva

O broker de conteúdo é a única peça autorizada a abrir arquivos do consumidor.
Ele não descobre caminhos: recebe o inventário produzido pelo broker de escopo.

## Processo

Para cada entrada autorizada, o broker:

1. verifica a extensão concedida pelo manifesto;
2. resolve novamente o caminho dentro da raiz;
3. rejeita links simbólicos;
4. abre somente arquivo regular, solicitando `O_NOFOLLOW` quando disponível;
5. aplica o limite antes e durante a leitura;
6. calcula SHA-256;
7. decodifica UTF-8 somente quando `content_access: text`;
8. produz uma requisição compatível com o schema fechado.

Arquivos grandes, binários, simbólicos ou incompatíveis são omitidos e registrados
no relatório de auditoria.

## O que o plugin recebe

O plugin recebe somente:

- caminho relativo;
- tamanho efetivamente lido;
- SHA-256;
- texto autorizado;
- IDs das regras atribuídas.

A raiz física, configuração, credenciais e relatório interno do broker não fazem
parte da requisição.

## Auditoria

O broker registra arquivos considerados e entregues, bytes lidos, omissões e a
garantia `project_root_disclosed: false`.

Esta é uma mediação de acesso para verificadores internos confiáveis. Ela não
substitui a futura sandbox necessária para código de terceiros.
