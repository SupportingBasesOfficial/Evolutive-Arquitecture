# Governança do repositório

A Constituição não pode depender apenas de disciplina humana para proteger sua própria fonte. O estado desejado do repositório é declarado em `governance/repository.yaml` e validado por `schema/repository-governance.schema.json`.

## Estado desejado

Para `main`, a política canônica exige:

- toda integração passa por pull request;
- somente squash merge é admitido como estratégia normativa;
- os checks `validate (ubuntu-latest)` e `validate (windows-latest)` são obrigatórios;
- conversas de revisão precisam estar resolvidas;
- histórico linear é obrigatório;
- force push e exclusão da branch são bloqueados;
- não existem atores com bypass permanente;
- branches de trabalho são preservadas após merge, salvo decisão explícita separada.

O mecanismo preferido no GitHub é um repository ruleset direcionado a `refs/heads/main`.

## Duas camadas de evidência

Há uma separação obrigatória entre contrato interno e enforcement do provedor.

### 1. Contrato interno

`scripts/validate_repository_governance.py` valida o arquivo de política e confirma que os nomes de checks obrigatórios correspondem aos checks realmente produzidos pelo workflow canônico `.github/workflows/validate-rules.yml`.

Esse validador faz parte de `scripts/validate_repository.py`. Portanto, drift entre política e CI quebra o gate de integração/publicação.

### 2. Enforcement externo

A existência do contrato interno não prova que o GitHub está bloqueando pushes diretos, merges inadequados ou bypasses. Essa garantia só existe quando o estado do provedor foi configurado e auditado.

O enforcement externo é um controle administrativo do GitHub e deve ser tratado como uma fronteira distinta. Se a credencial usada pela automação não possui permissão administrativa para ler ou escrever branch protection/rulesets, o sistema deve declarar essa limitação em vez de assumir conformidade.

## Estado observado nesta fase

Na inspeção que originou este contrato:

- nenhum repository ruleset estava configurado;
- `main` aparecia sem proteção ativa;
- o repositório permitia merge commit, rebase e squash no nível global;
- a integração disponível possuía administração sobre conteúdo e PRs, mas a leitura do endpoint de branch protection retornou acesso negado e nenhuma ação administrativa de ruleset/protection estava disponível.

Por isso, esta fase torna o estado desejado inequívoco e testável dentro do código, mas não declara o enforcement externo como concluído.

## Regra de verdade

`governance/repository.yaml` descreve **o que deve ser verdade**.

O estado configurado no GitHub demonstra **se isso está sendo imposto**.

Um nunca substitui o outro.

## Mudanças futuras

Qualquer alteração em nomes de jobs, estratégia de merge, regras de proteção ou bypass deve modificar primeiro o contrato canônico e seus testes. Mudanças administrativas no provedor precisam ser auditadas contra esse contrato e não podem silenciosamente redefinir a política constitucional.
