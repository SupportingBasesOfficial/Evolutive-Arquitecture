# Modelo de adoção

## Papéis separados

Este repositório é o **produtor da Constituição**. Ele mantém regras, schemas,
testes e ferramentas de publicação.

Um projeto que adota a Constituição é um **consumidor**. Ele não copia a estrutura
interna deste repositório nem permite que o catálogo controle sua organização física.

## Fronteiras

Há três superfícies independentes:

1. **Catálogo normativo** — arquivos em `rules/`, validados pelo schema de regras.
2. **Ferramenta de conformidade** — código executável, validado por testes próprios.
3. **Projeto consumidor** — código e registros de governança analisados somente por entradas e raízes explícitas.

O schema das regras não valida o código do validador. Os testes do validador
exercitam a ferramenta com fixtures controladas; eles não transformam a ferramenta
em uma regra constitucional.

## Superfície mínima no consumidor

A adoção mínima exige um único arquivo isolado. Exceções, quando existirem, ficam
em uma subárea própria de governança:

```text
projeto/
├── código e estrutura próprios
└── .evolutive/
    ├── config.yaml
    └── exceptions/            # opcional
        └── EXC-0001.yaml
```

O ponto de partida é `templates/project-config.yaml`. O arquivo fixa:

- uma versão semântica da Constituição;
- a URL exata do bundle daquela versão;
- o SHA-256 esperado;
- os perfis ativados;
- raízes relativas e específicas que podem ser analisadas;
- exclusões explícitas;
- modo `report` ou `enforce`.

Quando uma regra ativa admitir exceção, o consumidor pode usar o contrato descrito
em `docs/EXCEPTION_GOVERNANCE.md`. Esses registros pertencem ao consumidor e não
são enviados ao checker.

## Garantias de isolamento

A configuração é rejeitada quando:

- uma raiz é `.`, absoluta ou contém `..`;
- uma raiz tenta incluir `.evolutive/`;
- a URL do artefato não corresponde à versão declarada;
- `.evolutive/**` não está entre as exclusões;
- o perfil universal não está ativado.

O validador de configuração lê somente o arquivo indicado. A inspeção de código
ocorre depois, por brokers que aplicam as raízes e exclusões já aprovadas.

O validador de exceções abre somente `.evolutive/exceptions/`, recusa links
simbólicos e registros fora do contrato e não concede ao checker acesso a essa área.

## Raiz de confiança

Cada release produz um pacote versionado com checksum. O consumidor fixa versão,
URL e checksum; atualizações são decisões explícitas.

```text
schema de regras -> valida o catálogo
testes -> validam as ferramentas
release versionada -> entrega o catálogo
configuração -> fixa a release e limita a análise
exceções -> registram desvios concretos sem alterar a regra universal
```

## Estado atual

A implementação já verifica a origem constitucional, produz o plano, inspeciona
conteúdo por brokers, executa checkers internos registrados e emite relatório com
cadeia de evidências. A governança de ciclo de vida impede promoções de regra sem
decisão auditável, e o contrato de exceções limita desvios do consumidor antes de
qualquer regra ser promovida para enforcement ativo.
