# Evolutive-Arquitecture

Constituição arquitetural evolutiva: diretrizes universais, verificáveis e versionadas para orientar decisões de arquitetura e engenharia.

## Estado atual

O projeto está em sua fase fundacional. A [Meta-Constituição](./META-CONSTITUTION.md) define como as regras são criadas, interpretadas, aplicadas e evoluídas.

O formato das regras é definido pelo [schema canônico](./schema/rule.schema.json), acompanhado de um [template de autoria](./templates/rule.yaml).

## Primeiras propostas universais

As regras abaixo estão em estado `proposed` e ainda não possuem força ativa:

- [ARCH-001 — Núcleo independente de detalhes externos](./rules/universal/ARCH-001.yaml)
- [ARCH-002 — Dependências apontam para políticas mais estáveis](./rules/universal/ARCH-002.yaml)
- [MOD-001 — Interações entre módulos usam contratos explícitos](./rules/universal/MOD-001.yaml)
- [INT-001 — Tecnologias externas são integradas por adaptadores](./rules/universal/INT-001.yaml)
