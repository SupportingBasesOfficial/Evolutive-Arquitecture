# Broker de escopo

## Responsabilidade

O broker é a única peça autorizada a enumerar arquivos do projeto consumidor.
Ele recebe a configuração já validada e produz um inventário limitado.

Plugins verificadores não receberão a raiz do projeto. Eles receberão somente
entradas derivadas desse inventário.

## Garantias atuais

O broker:

- entra apenas nas raízes declaradas em `scope.roots`;
- aplica as exclusões antes de disponibilizar entradas;
- rejeita raízes que sejam links simbólicos;
- ignora qualquer arquivo ou diretório que seja link simbólico;
- confirma que caminhos resolvidos continuam dentro do projeto;
- limita a quantidade de arquivos;
- registra raízes ausentes sem tentar descobri-las;
- coleta apenas caminho relativo e tamanho;
- declara `content_access.performed: false` e `bytes_read: 0`.

## Limite de segurança

O broker cria uma fronteira lógica e testável, mas ainda não é uma sandbox de
segurança para código hostil. Plugins de terceiros não confiáveis exigirão um
runtime isolado, sem acesso direto ao sistema de arquivos ou à rede.

Até essa sandbox existir, somente verificadores mantidos e revisados neste
repositório poderão ser executados.

## Fluxo futuro

```text
configuração validada
        |
        v
broker de escopo
        |
        v
inventário permitido
        |
        v
broker de conteúdo com limites
        |
        v
plugin verificador isolado
        |
        v
evidências
```

A próxima etapa será definir o contrato de entrada e saída dos plugins sem ainda
executar código de terceiros.
