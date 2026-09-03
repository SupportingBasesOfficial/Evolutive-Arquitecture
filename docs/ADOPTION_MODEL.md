# Modelo de adoção

## Papéis separados

Este repositório é o **produtor da Constituição**. Ele mantém regras, schemas,
testes e ferramentas de publicação.

Um projeto que adota a Constituição é um **consumidor**. Ele não deve copiar a
estrutura interna deste repositório nem permitir que o catálogo controle sua
organização física.

## Fronteiras

Há três superfícies independentes:

1. **Catálogo normativo** — arquivos em `rules/`, validados pelo schema.
2. **Ferramenta de conformidade** — código executável, validado por testes próprios.
3. **Projeto consumidor** — código analisado somente por entradas e raízes explícitas.

O schema valida regras. Ele não valida o código do validador.

Os testes do validador exercitam a ferramenta com fixtures controladas. Eles não
transformam a ferramenta em uma regra constitucional.

A futura verificação de um consumidor deve receber explicitamente:

- versão imutável da Constituição;
- perfis ativados;
- raízes de código que podem ser analisadas;
- exclusões;
- parâmetros específicos do projeto.

Uma ferramenta de conformidade **não deve** percorrer a raiz inteira por padrão.

## Superfície mínima no consumidor

A adoção deverá exigir, no máximo, um arquivo isolado:

```text
projeto/
├── código e estrutura próprios
└── .evolutive/
    └── config.yaml
```

O diretório `.evolutive/` conterá apenas configuração do consumidor. Regras,
schemas e executáveis virão de uma release versionada e verificada, fora da árvore
de código analisada.

## Raiz de confiança

Cada release deverá produzir um pacote imutável com checksum. O consumidor fixa
uma versão e seu checksum; atualizações serão decisões explícitas.

O ciclo de confiança será:

```text
schema -> valida o catálogo
testes -> validam a ferramenta
release imutável -> entrega catálogo e ferramenta
configuração -> limita a análise do consumidor
```

## Estado atual

O repositório possui validação de integridade do catálogo. A validação de projetos
consumidores ainda não foi implementada e não deve ser inferida a partir do
workflow atual.
