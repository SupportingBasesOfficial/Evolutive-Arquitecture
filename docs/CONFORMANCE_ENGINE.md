# Motor de conformidade

## Estágios

O motor é dividido em estágios para impedir que descoberta, confiança e inspeção
se misturem:

1. **Validar configuração** — lê somente `.evolutive/config.yaml`.
2. **Verificar fonte** — confere SHA-256, versão e manifesto do bundle.
3. **Planejar** — seleciona perfis, regras e raízes autorizadas.
4. **Inspecionar** — futuramente executará verificadores somente nas raízes do plano.
5. **Relatar** — produzirá evidências sem modificar o projeto.

Esta versão implementa apenas os três primeiros estágios.

## Garantia de não inspeção

`scripts/plan_compliance.py` não enumera nem lê arquivos das raízes do consumidor.
O resultado declara explicitamente:

```json
{
  "inspection": {
    "performed": false,
    "files_read": 0,
    "reason": "planning stage only"
  }
}
```

Os testes criam um arquivo sentinela dentro de `src/` e comprovam que seu
conteúdo não aparece no plano.

## Regras propostas

Regras com status `proposed` aparecem no plano para revisão, mas recebem
`eligible_for_enforcement: false`. Somente regras `active` poderão bloquear
um projeto quando o estágio de inspeção existir.

## Próxima fronteira

Verificadores automáticos deverão ser plugins separados por linguagem ou
plataforma. Cada plugin receberá a lista já resolvida de raízes autorizadas; não
terá autoridade para redescobrir a raiz do projeto.
