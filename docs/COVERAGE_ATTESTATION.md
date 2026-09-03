# Coverage attestation

## Propósito

Coverage attestation separa duas perguntas que não podem ser confundidas:

1. **O checker encontrou uma violação?**
2. **A observação foi suficientemente completa para sustentar uma conclusão positiva?**

O checker universal continua responsável apenas pela primeira pergunta. O attestor não altera findings, não muda status de regra e não transforma ausência de finding em `pass`.

## Cadeia de autoridade

A cadeia confiável é:

1. `scope_broker` constrói o inventário autorizado;
2. `adapter_broker` vincula esse inventário por `inventory_sha256` e os conteúdos efetivamente entregues por `delivered_content_sha256`;
3. o adapter produz observações, coverage e erros;
4. o assembler produz `architecture-evidence.yaml`;
5. o coverage attestor **reexecuta o pipeline completo** contra o projeto atual e recusa evidence que não seja exatamente reproduzível;
6. somente depois avalia suficiência dentro do escopo técnico do manifesto do adapter.

Evidence stale, editada ou forjada não recebe verdict `insufficient`: ela é recusada como inválida para attestation.

## Escopo da suficiência

`evaluation.verdict: sufficient` significa apenas:

> a observação é suficiente dentro do conjunto de extensões explicitamente suportado pela versão e implementação do adapter identificadas na attestation.

Não significa que todo o projeto, toda a linguagem ou todo o ecossistema foram analisados.

A attestation registra:

- ecosystem;
- adapter id e versão;
- SHA-256 da implementação do adapter;
- extensões efetivamente suportadas;
- SHA-256 da evidence;
- SHA-256 do inventário autorizado;
- SHA-256 dos conteúdos entregues;
- id, versão e SHA-256 da implementação do attestor.

## Critérios de suficiência

Todos devem ser verdadeiros:

- `no_inventory_gaps`: nenhum root autorizado ausente e nenhum symlink foi pulado pelo inventário;
- `no_relevant_broker_skips`: nenhum arquivo dentro do escopo de extensões do adapter deixou de ser entregue;
- `all_delivered_files_analyzed`: todo arquivo entregue foi analisado pelo adapter;
- `no_observation_errors`: nenhum erro lexical/de parsing/observação ocorreu;
- `no_unresolved_references`: nenhuma referência relevante ficou sem resolução.

Arquivos com extensões fora do manifesto podem aparecer como `extension_not_allowed` e não tornam a attestation insuficiente, porque estão explicitamente fora daquele escopo técnico. O attestor rejeita um audit que tente marcar uma extensão suportada como `extension_not_allowed`.

## Integridade versus incompletude

Falhas de integridade/proveniência são erros:

- evidence não corresponde à execução fresca;
- manifesto não corresponde ao producer;
- versões/ecossistema divergem;
- audit não fecha contabilmente;
- arquivo suportado foi escondido como extensão não permitida.

Lacunas legítimas de observação produzem `insufficient`:

- root ausente ou symlink pulado;
- arquivo suportado não entregue;
- arquivo entregue não analisado;
- erro de observação;
- referência não resolvida.

## Relação com `pass`

Neste estágio **nenhuma attestation é input do checker** e nenhum mecanismo transforma `sufficient + no findings` em `pass`.

Uma futura evolução poderá introduzir um result aggregator separado. Antes disso, será necessário definir explicitamente:

- quais regras aceitam coverage attestation como pré-condição de pass;
- quais adapters/ecossistemas possuem precisão suficiente;
- como múltiplos adapters compõem coverage de projetos multi-ecossistema;
- como preservar autoridade e provenance no CI;
- como invalidar attestations quando qualquer parte do snapshot ou tooling muda.

Até essa autoridade existir e ser governada, `ARCH-002` e `MOD-001` permanecem `fail_only` e `not_ready`.
