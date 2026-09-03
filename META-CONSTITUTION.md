# Meta-Constituição

**Status:** Evolutiva  
**Versão:** 0.2.0  
**Idioma normativo:** Português

## 1. Propósito

Este documento governa a criação, interpretação, aplicação e evolução das diretrizes arquiteturais e dos padrões de engenharia deste repositório.

A Constituição deve transformar princípios de engenharia em regras objetivas, verificáveis e evolutivas. Ela não deve impor tecnologias específicas como leis universais nem tentar prever todas as decisões futuras.

## 2. Autoridade normativa

Os termos abaixo têm significado obrigatório:

- **DEVE** / **NÃO DEVE**: requisito obrigatório.
- **DEVERIA** / **NÃO DEVERIA**: recomendação forte; desvios exigem justificativa.
- **PODE**: opção permitida.
- **NORMATIVO**: conteúdo que estabelece obrigação.
- **INFORMATIVO**: explicação, exemplo ou orientação sem força normativa.

Em caso de conflito, prevalece a regra mais específica, desde que ela não enfraqueça uma regra universal sem uma exceção aprovada.

## 3. Camadas de governança

As regras devem pertencer a uma única camada:

1. **Universal** — independente de linguagem, framework, plataforma ou segmento.
2. **Projeto** — decisões e invariantes de um produto específico.
3. **Tecnologia** — regras próprias de uma linguagem, framework ou ferramenta.
4. **Plataforma** — regras próprias de web, mobile, backend, desktop, IoT ou ambiente operacional.

Uma regra específica pode tornar uma regra superior mais rigorosa. Ela não pode torná-la menos rigorosa sem registrar uma exceção.

## 4. Formato obrigatório de uma regra

Toda regra normativa DEVE conter:

- **ID estável**
- **Título**
- **Camada**
- **Força normativa**
- **Enunciado verificável**
- **Justificativa**
- **Escopo**
- **Critério de conformidade**
- **Forma de enforcement**
- **Exemplos conformes e não conformes**
- **Exceções permitidas**
- **Status e versão de introdução**

IDs publicados NÃO DEVEM ser reutilizados, mesmo após revogação.

## 5. Critérios de admissibilidade

Uma proposta somente pode virar regra quando:

- protege uma qualidade arquitetural ou operacional identificável;
- pode ser interpretada de forma consistente por humanos e agentes;
- possui critério observável de conformidade;
- distingue obrigação universal de preferência tecnológica;
- explicita custos, limites e exceções relevantes;
- não duplica nem contradiz uma regra existente.

Preferências sem impacto arquitetural demonstrável NÃO DEVEM ser promovidas a regras universais.

## 6. Enforcement

Cada regra DEVE declarar um dos níveis:

- **Automático** — validável por ferramenta em todos os casos relevantes.
- **Semiautomático** — ferramenta detecta candidatos e uma pessoa decide.
- **Revisão** — verificação humana ou por agente com evidência registrada.
- **Declarativo** — ainda não automatizável; exige justificativa explícita de conformidade.

Sempre que viável, regras obrigatórias DEVEM possuir enforcement automático. Falhas de ferramenta não transformam conformidade em opcional.

## 7. Exceções

Uma exceção DEVE ser explícita, limitada e rastreável. O registro DEVE incluir:

- regra afetada;
- contexto e justificativa;
- responsável;
- riscos aceitos;
- controles compensatórios;
- escopo;
- data de expiração ou condição de revisão.

Exceções permanentes NÃO DEVEM ser usadas para ocultar uma regra inadequada. Se o mesmo desvio se repetir, a regra deve ser revisada.

## 8. Evolução e compatibilidade

A Constituição usa versionamento semântico:

- **MAJOR**: mudança incompatível em obrigação existente;
- **MINOR**: nova regra ou ampliação compatível;
- **PATCH**: esclarecimento sem mudança normativa.

Alterações NÃO DEVEM apagar o histórico decisório. Regras podem ser propostas, experimentais, ativas, depreciadas ou revogadas.

Uma mudança normativa DEVE declarar motivação, impacto, plano de adoção e, quando necessário, período de transição.

## 9. Processo de mudança

Toda mudança normativa deve seguir:

1. proposta com problema e evidências;
2. análise de conflitos e impacto;
3. revisão;
4. decisão registrada;
5. publicação versionada;
6. adoção e enforcement;
7. avaliação posterior quando aplicável.

Mudanças editoriais que não alteram significado podem seguir processo simplificado.

## 10. Princípios de interpretação

Na dúvida:

- preservar limites arquiteturais;
- favorecer alta coesão e baixo acoplamento;
- manter decisões tecnológicas reversíveis;
- tornar contratos explícitos;
- exigir evidência proporcional ao risco;
- preferir evolução compatível a rupturas;
- evitar complexidade sem necessidade demonstrada.

## 11. Escopo desta versão

A versão 0.2.0 inaugura a adoção controlada das primeiras regras universais de arquitetura e engenharia. `ARCH-001`, `ARCH-002`, `MOD-001` e `INT-001` passam ao estado `experimental` para coleta de evidências, avaliação de aplicabilidade, falsos positivos, custos e lacunas de enforcement.

Regras experimentais ainda não são elegíveis para enforcement bloqueante. A promoção futura para `active` depende de decisão auditável separada e de readiness compatível com o mecanismo declarado por cada regra.
